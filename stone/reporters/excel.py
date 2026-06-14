"""Excel reporter."""

from pathlib import Path

import xlsxwriter

from stone import __version__
from stone.selector.engine import SelectionResult


class ExcelReporter:
    """Render xlsx reports with several sheets."""

    DISCLAIMER = "⚠️ 本表为按预设规则的算术计算结果，非投资建议。买卖决策请自行判断。"

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.xlsx"

        workbook = xlsxwriter.Workbook(str(out))
        bold = workbook.add_format({"bold": True, "bg_color": "#D9EAD3", "border": 1})
        text_fmt = workbook.add_format({"num_format": "@"})
        score_fmt = workbook.add_format({"num_format": "0.0", "align": "center"})
        note_fmt = workbook.add_format({"italic": True})
        disclaimer_fmt = workbook.add_format({"bg_color": "#FFF2CC"})

        ws_top = workbook.add_worksheet("Top名单")
        headers = [
            "排名",
            "代码",
            "名称",
            "行业",
            "评分",
            "建议金额",
            "建议股数",
            "止损价",
            "止盈价",
            "入选理由",
        ]
        for col, header in enumerate(headers):
            ws_top.write(0, col, header, bold)
        ws_top.set_column(1, 1, 12, text_fmt)

        for index, score in enumerate(result.final_picks, start=1):
            row = index
            ws_top.write_number(row, 0, index)
            ws_top.write_string(row, 1, score.code)
            ws_top.write_string(row, 2, score.name)
            ws_top.write_string(row, 3, score.industry)
            ws_top.write_number(row, 4, score.score, score_fmt)
            if index - 1 < len(result.position_plans):
                plan = result.position_plans[index - 1]
                ws_top.write_number(row, 5, plan.amount)
                ws_top.write_number(row, 6, plan.shares)
                if plan.stop_loss_price is not None:
                    ws_top.write_number(row, 7, plan.stop_loss_price)
                if plan.take_profit_price is not None:
                    ws_top.write_number(row, 8, plan.take_profit_price)
            reasons = " + ".join(
                name for name, value in score.normalized_values.items() if value >= 80.0
            )
            ws_top.write_string(row, 9, reasons)

        ws_top.write(
            len(result.final_picks) + 2, 1, "← 可直接复制代码列到涨乐财富通批量添加自选", note_fmt
        )
        ws_top.write(len(result.final_picks) + 4, 0, self.DISCLAIMER, disclaimer_fmt)

        ws_factor = workbook.add_worksheet("因子明细")
        all_factors: set[str] = set()
        for score in result.final_picks:
            all_factors.update(score.normalized_values.keys())
        factor_cols = sorted(all_factors)
        ws_factor.write_row(0, 0, ["排名", "代码", "名称", "总分"] + factor_cols, bold)
        for row, score in enumerate(result.final_picks, start=1):
            ws_factor.write_number(row, 0, row)
            ws_factor.write_string(row, 1, score.code)
            ws_factor.write_string(row, 2, score.name)
            ws_factor.write_number(row, 3, score.score, score_fmt)
            for col, factor_name in enumerate(factor_cols, start=4):
                factor_value = score.normalized_values.get(factor_name)
                if factor_value is not None:
                    ws_factor.write_number(row, col, factor_value, score_fmt)

        ws_meta = workbook.add_worksheet("元信息")
        info: list[tuple[str, str | int]] = [
            ("策略名称", result.strategy_name),
            ("目标日期", result.target_date.isoformat()),
            ("Stone 版本", __version__),
            ("股池大小", result.universe_size),
            ("评分成功", result.scored_size),
            ("通过过滤", result.passed_size),
            ("最终入选", len(result.final_picks)),
            ("失败数", len(result.failed_codes)),
            ("免责声明", self.DISCLAIMER),
        ]
        for row, (key, meta_value) in enumerate(info):
            ws_meta.write(row, 0, key, bold)
            ws_meta.write(row, 1, str(meta_value))

        ws_failed = workbook.add_worksheet("失败股票")
        ws_failed.write_row(0, 0, ["代码", "原因"], bold)
        for row, (code, reason) in enumerate(result.failed_codes, start=1):
            ws_failed.write_string(row, 0, code)
            ws_failed.write_string(row, 1, reason)

        workbook.close()
        return out

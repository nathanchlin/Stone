"""JSON reporter."""

import json
from pathlib import Path

from stone import __version__
from stone.selector.engine import SelectionResult


class JsonReporter:
    """Render machine-readable JSON reports."""

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": {
                "strategy_name": result.strategy_name,
                "target_date": result.target_date.isoformat(),
                "stone_version": __version__,
            },
            "summary": {
                "universe_size": result.universe_size,
                "scored_size": result.scored_size,
                "passed_size": result.passed_size,
                "top_n": len(result.final_picks),
                "failed_count": len(result.failed_codes),
            },
            "picks": [
                {
                    "rank": index + 1,
                    "code": score.code,
                    "name": score.name,
                    "industry": score.industry,
                    "score": score.score,
                    "factor_scores": score.normalized_values,
                }
                for index, score in enumerate(result.final_picks)
            ],
            "position_plans": [
                {
                    "code": plan.code,
                    "amount": plan.amount,
                    "shares": plan.shares,
                    "stop_loss_price": plan.stop_loss_price,
                    "take_profit_price": plan.take_profit_price,
                }
                for plan in result.position_plans
            ],
            "failed": [{"code": code, "reason": reason} for code, reason in result.failed_codes],
        }
        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

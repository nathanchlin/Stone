"""Selection engine orchestration."""

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from tqdm import tqdm

from stone.data.cache.parquet_store import ParquetStore
from stone.data.fetchers.base import DataFetcher
from stone.data.universe import UniverseRules, get_active_universe
from stone.selector.constraints import ConstraintSolver
from stone.selector.criterion import safe_eval_criterion
from stone.selector.factors.base import FactorContext
from stone.selector.position_sizing import PositionPlan, PositionRules, PositionSizer
from stone.selector.scoring import ScoringEngine, StockScore
from stone.selector.strategy import Strategy

log = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    """Final output of a selection run."""

    strategy_name: str
    target_date: date
    universe_size: int
    scored_size: int
    passed_size: int
    final_picks: list[StockScore] = field(default_factory=list)
    position_plans: list[PositionPlan] = field(default_factory=list)
    failed_codes: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.target_date}] {self.strategy_name}\n"
            f"  股池:    {self.universe_size} → 评分成功: {self.scored_size} "
            f"→ 通过过滤: {self.passed_size} → 最终: {len(self.final_picks)}\n"
            f"  失败:    {len(self.failed_codes)} 只"
        )


class SelectionEngine:
    """Orchestrate universe loading, scoring, filtering and sizing."""

    def __init__(
        self,
        strategy: Strategy,
        store: ParquetStore,
        fetcher: DataFetcher,
        position_rules: PositionRules | None = None,
    ):
        self.strategy = strategy
        self.store = store
        self.fetcher = fetcher
        self.scorer = ScoringEngine(strategy.scoring)
        self.constraint_solver = ConstraintSolver(strategy.constraints)
        self.position_sizer = PositionSizer(position_rules) if position_rules else None
        self.filters = strategy.filters
        self.failed_codes: list[tuple[str, str]] = []
        self._universe_snapshot = None

    def _cache_kline_history(self, code: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return

        payload = frame.copy()
        payload["code"] = code
        payload["date"] = pd.to_datetime(payload["date"], errors="coerce").dt.date
        payload = payload.dropna(subset=["date"])
        if payload.empty:
            return

        for target, group in payload.groupby("date"):
            existing = self.store.read_kline(target)
            combined = pd.concat([existing, group], ignore_index=True) if not existing.empty else group
            combined = combined.drop_duplicates(subset=["code"], keep="last")
            self.store.write_kline(target, combined)

    def run(self, target_date: date) -> SelectionResult:
        log.info("开始选股，target_date=%s", target_date)
        universe = self._load_universe(target_date)
        scores, failed = self._compute_scores_parallel(universe, target_date)
        self.failed_codes.extend(failed)

        passed = [score for score in scores if self._passes_all_filters(score)]
        ranked = sorted(passed, key=lambda item: item.score, reverse=True)
        above = [score for score in ranked if score.score >= self.strategy.output.min_score]
        constrained = self.constraint_solver.apply(above)
        top_n = constrained[: self.strategy.output.top_n]

        position_plans: list[PositionPlan] = []
        if self.position_sizer and top_n:
            close_prices = self._fetch_close_prices([score.code for score in top_n], target_date)
            position_plans = self.position_sizer.allocate(top_n, close_prices=close_prices)

        return SelectionResult(
            strategy_name=self.strategy.meta.name,
            target_date=target_date,
            universe_size=len(universe),
            scored_size=len(scores),
            passed_size=len(passed),
            final_picks=top_n,
            position_plans=position_plans,
            failed_codes=self.failed_codes.copy(),
        )

    def _load_universe(self, target_date: date) -> list[str]:
        df = self.store.read_latest_before("universe", target_date)
        if df.empty:
            df = self.fetcher.list_universe(target_date)
            if not df.empty:
                self.store.write("universe", target_date, df)
        self._universe_snapshot = df.copy() if not df.empty else None
        if df.empty:
            return []

        rules_path = self.strategy.universe.rules_file
        if rules_path.exists():
            rules = UniverseRules.from_yaml(rules_path)
        else:
            rules = UniverseRules(include_boards=list(self.strategy.universe.include_boards))
        if rules.include_boards and not self.strategy.universe.include_boards:
            self.strategy.universe.include_boards = list(rules.include_boards)
        filtered = get_active_universe(df, target_date, rules)
        return filtered

    def _passes_all_filters(self, score: StockScore) -> bool:
        for rule in self.filters:
            raw = score.raw_values.get(rule.factor)
            if raw is None:
                return False
            try:
                if not safe_eval_criterion(rule.criterion, raw):
                    return False
            except ValueError:
                return False
        return True

    def _compute_scores_parallel(
        self,
        universe: list[str],
        target_date: date,
    ) -> tuple[list[StockScore], list[tuple[str, str]]]:
        scores: list[StockScore] = []
        failed: list[tuple[str, str]] = []
        for code in tqdm(universe, desc="打分中"):
            try:
                ctx = self._build_context(code, target_date)
                if ctx is None:
                    failed.append((code, "missing data"))
                    continue
                score = self.scorer.score_one(ctx)
                self._annotate_filter_values(score, ctx)
                scores.append(score)
            except Exception as exc:  # noqa: BLE001
                failed.append((code, str(exc)))
        return scores, failed

    def _annotate_filter_values(self, score: StockScore, ctx: FactorContext) -> None:
        """Compute filter-only factors and merge into score.raw_values.

        Filter factors (e.g. roe_above_15, revenue_growth_positive) are not in
        scoring.factors, so score_one does not compute them. Without this
        annotation, _passes_all_filters looks up missing keys and rejects
        every stock.
        """
        from stone.selector.factors import REGISTRY

        for rule in self.filters:
            if rule.factor in score.raw_values and score.raw_values[rule.factor] is not None:
                continue
            factor_cls = REGISTRY.get(rule.factor)
            if factor_cls is None:
                score.raw_values[rule.factor] = None
                continue
            try:
                score.raw_values[rule.factor] = factor_cls().compute(ctx)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "filter factor %s failed for %s: %s: %s",
                    rule.factor,
                    ctx.code,
                    type(exc).__name__,
                    exc,
                )
                score.raw_values[rule.factor] = None

    def _build_context(self, code: str, target_date: date) -> FactorContext | None:
        history = self.strategy.universe.history_days
        # Convert trading days to calendar days: 1 trading day ≈ 1.5 calendar days
        # (weekends + holidays). Buffer +30 for year-boundary safety.
        calendar_lookback = int(history * 1.5) + 30
        start = target_date.fromordinal(target_date.toordinal() - calendar_lookback)
        kline_df = self.store.read_kline_range(start, target_date)
        kline = pd.DataFrame()
        if not kline_df.empty and "code" in kline_df.columns:
            kline = kline_df[kline_df["code"] == code].drop(columns=["_cache_date"], errors="ignore")
        if kline.empty:
            try:
                fetched = self.fetcher.get_daily_kline(code, start, target_date)
            except Exception:  # noqa: BLE001
                return None
            if fetched.empty:
                return None
            self._cache_kline_history(code, fetched)
            kline = fetched.copy()
        if kline.empty:
            return None
        kline = kline.sort_values("date").reset_index(drop=True)

        financial = self.store.read_latest_before("financial", target_date)
        if not financial.empty and "code" in financial.columns:
            financial = financial[financial["code"].astype(str) == code]

        moneyflow = self.store.read_latest_before("moneyflow", target_date)
        if not moneyflow.empty and "code" in moneyflow.columns:
            moneyflow = moneyflow[moneyflow["code"].astype(str) == code]

        name = code
        industry = "unknown"
        if self._universe_snapshot is not None and not self._universe_snapshot.empty:
            meta = self._universe_snapshot[self._universe_snapshot["code"].astype(str) == code]
            if not meta.empty:
                if "name" in meta.columns:
                    name = str(meta.iloc[0]["name"])
                if "industry" in meta.columns and pd.notna(meta.iloc[0]["industry"]):
                    industry = str(meta.iloc[0]["industry"])

        return FactorContext(
            code=code,
            name=name,
            industry=industry,
            today=target_date,
            kline=kline,
            financial=financial,
            moneyflow=moneyflow,
        )

    def _fetch_close_prices(self, codes: list[str], target_date: date) -> list[float]:
        prices: list[float] = []
        kline = self.store.read_kline_latest_before(target_date)
        for code in codes:
            row = kline[kline["code"].astype(str) == code] if not kline.empty else kline
            prices.append(float(row["close"].iloc[0]) if not row.empty else 0.0)
        return prices

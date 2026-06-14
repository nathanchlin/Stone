"""CLI entry for the Stone project."""

from datetime import date
from pathlib import Path

import click

from stone.logging_setup import setup_logging
from stone.selector.strategy import load_strategy


@click.group()
def app() -> None:
    """Stone: A-stock personal investment research assistant."""


@app.command()
@click.option("--retry-failed", is_flag=True, help="Retry previously failed dates")
@click.option(
    "--backfill",
    nargs=2,
    type=str,
    help="Backfill date range: START END (YYYY-MM-DD)",
)
def update(retry_failed: bool, backfill: tuple[str, str] | None) -> None:
    """Incremental data update."""
    from stone.data.cache.parquet_store import ParquetStore
    from stone.data.fetchers.akshare_fetcher import AkshareFetcher
    from stone.data.incremental import IncrementalUpdater

    setup_logging()
    store = ParquetStore(Path("data_cache"))
    fetcher = AkshareFetcher()
    if backfill:
        start_str, end_str = backfill
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
        updater = IncrementalUpdater(store=store, fetcher=fetcher, lookback_days=0)
        calendar = fetcher.get_trade_calendar(start, end)
        success = failed = skipped = 0
        for target in calendar:
            report = updater.update_daily(target)
            success += len(report.success_dates)
            failed += len(report.failed_dates)
            skipped += len(report.skipped_dates)
            click.echo(report.summary())
        click.echo(f"Backfill done: success={success} failed={failed} skipped={skipped}")
    else:
        updater = IncrementalUpdater(store=store, fetcher=fetcher, lookback_days=0)
        target = date.today()
        if retry_failed:
            click.echo("retry_failed=true")
        report = updater.update_daily(target)
        click.echo(report.summary())


@app.command()
@click.option("--strategy", required=False, help="Strategy YAML name (without extension)")
@click.option("--date", "target_date", type=str, default=None, help="YYYY-MM-DD")
@click.option("--all-strategies", is_flag=True, help="Run all strategies in config/strategies/")
@click.option("--report-dir", default="reports", help="Output directory for reports")
def select(
    strategy: str | None, target_date: str | None, all_strategies: bool, report_dir: str
) -> None:
    """Run stock selection with the given strategy."""
    from stone.data.cache.parquet_store import ParquetStore
    from stone.data.fetchers.akshare_fetcher import AkshareFetcher
    from stone.reporters.excel import ExcelReporter
    from stone.reporters.html import HtmlReporter
    from stone.reporters.json_reporter import JsonReporter
    from stone.reporters.markdown import MarkdownReporter
    from stone.selector.engine import SelectionEngine
    from stone.selector.position_sizing import PositionRules

    setup_logging()
    target = date.fromisoformat(target_date) if target_date else date.today()
    strategies_dir = Path("config/strategies")

    if all_strategies:
        files = sorted(strategies_dir.glob("*.yaml"))
    elif strategy:
        files = [strategies_dir / f"{strategy}.yaml"]
        if not files[0].exists():
            click.echo(f"Strategy not found: {files[0]}", err=True)
            raise click.Abort()
    else:
        click.echo("Must specify --strategy NAME or --all-strategies", err=True)
        raise click.Abort()

    store = ParquetStore(Path("data_cache"))
    fetcher = AkshareFetcher()
    out_dir = Path(report_dir)
    position_rules = None
    personal_rules = Path("config/personal/position_rules.yaml")
    if personal_rules.exists():
        position_rules = PositionRules.from_yaml(personal_rules)

    for strategy_file in files:
        click.echo(f"Running strategy: {strategy_file.stem}")
        config = load_strategy(strategy_file)
        engine = SelectionEngine(
            strategy=config,
            store=store,
            fetcher=fetcher,
            position_rules=position_rules,
        )
        result = engine.run(target)
        click.echo(result.summary())
        if not result.final_picks:
            click.echo("No picks produced. Check cached data completeness and factor/filter settings.")

        JsonReporter().render(result, out_dir)
        MarkdownReporter().render(result, out_dir)
        ExcelReporter().render(result, out_dir)
        HtmlReporter().render(result, out_dir)


@app.command()
def daily() -> None:
    """Daily pipeline: update + select + report."""
    from stone.data.cache.parquet_store import ParquetStore
    from stone.data.fetchers.akshare_fetcher import AkshareFetcher
    from stone.data.incremental import IncrementalUpdater

    setup_logging()
    target = date.today()
    click.echo(f"=== Daily pipeline {target} ===")

    store = ParquetStore(Path("data_cache"))
    fetcher = AkshareFetcher()
    report = IncrementalUpdater(store=store, fetcher=fetcher).update_daily(target)
    click.echo(report.summary())

    ctx = click.get_current_context()
    ctx.invoke(
        select,
        strategy=None,
        target_date=target.isoformat(),
        all_strategies=True,
        report_dir="reports",
    )


@app.command("list-strategies")
def list_strategies() -> None:
    """List available strategy files."""
    strategies_dir = Path("config/strategies")
    if not strategies_dir.exists():
        click.echo("(no strategies directory)")
        return
    yaml_files = sorted(strategies_dir.glob("*.yaml"))
    if not yaml_files:
        click.echo("(no strategies found)")
        return
    for strategy_file in yaml_files:
        click.echo(strategy_file.stem)


@app.command("validate-config")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate_config(path: Path) -> None:
    """Validate a strategy YAML file."""
    config = load_strategy(path)
    click.echo(f"Valid: {config.meta.name} v{config.meta.version}")
    return None


if __name__ == "__main__":
    app()

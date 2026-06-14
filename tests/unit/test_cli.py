from pathlib import Path

from click.testing import CliRunner

from stone.cli import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "select" in result.output
    assert "update" in result.output


def test_cli_list_strategies():
    runner = CliRunner()
    result = runner.invoke(app, ["list-strategies"])
    assert result.exit_code == 0
    assert "band_trend_v1" in result.output
    assert "starter_small_capital_v1" in result.output


def test_cli_validate_config_accepts_valid_file():
    runner = CliRunner()
    result = runner.invoke(app, ["validate-config", "config/strategies/band_trend_v1.yaml"])
    assert result.exit_code == 0
    assert "Valid: band_trend_v1" in result.output


def test_cli_select_requires_strategy_or_all_strategies():
    runner = CliRunner()
    result = runner.invoke(app, ["select"])
    assert result.exit_code != 0


def test_cli_select_missing_strategy_aborts():
    runner = CliRunner()
    result = runner.invoke(app, ["select", "--strategy", "missing_strategy"])
    assert result.exit_code != 0


def test_cli_validate_config_missing_file(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["validate-config", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code != 0

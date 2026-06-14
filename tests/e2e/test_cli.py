"""E2E tests for CLI invocation through subprocess."""

import subprocess
import sys


def test_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "select" in result.stdout
    assert "update" in result.stdout


def test_cli_list_strategies_lists_expected_files():
    result = subprocess.run(
        [sys.executable, "main.py", "list-strategies"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "band_trend_v1" in result.stdout
    assert "breakout_strong" in result.stdout
    assert "starter_small_capital_v1" in result.stdout
    assert "value_with_catalyst" in result.stdout


def test_cli_validate_config_accepts_valid_file():
    result = subprocess.run(
        [sys.executable, "main.py", "validate-config", "config/strategies/band_trend_v1.yaml"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Valid" in result.stdout

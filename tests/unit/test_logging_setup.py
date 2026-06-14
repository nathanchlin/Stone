import logging
from pathlib import Path

from stone.logging_setup import setup_logging


def test_setup_logging_creates_log_file(tmp_path: Path):
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file)

    logging.getLogger("test").info("hello world")

    assert log_file.exists()
    assert "hello world" in log_file.read_text(encoding="utf-8")


def test_setup_logging_format_contains_level_and_message(tmp_path: Path):
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file)

    logging.getLogger("test").warning("warn msg")

    content = log_file.read_text(encoding="utf-8")
    assert "WARNING" in content
    assert "warn msg" in content

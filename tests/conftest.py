"""Shared pytest fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_cache(tmp_path) -> Path:
    """Temporary data_cache directory."""
    cache = tmp_path / "data_cache"
    cache.mkdir()
    return cache

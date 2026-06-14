"""Custom exceptions for stone."""


class StoneError(Exception):
    """Base exception for all stone errors."""


class FactorError(StoneError):
    """Raised when a factor fails to compute."""


class DataError(StoneError):
    """Raised when data fetching/parsing fails."""


class ConfigError(StoneError):
    """Raised when configuration is invalid."""


class StrategyError(ConfigError):
    """Raised when strategy configuration is invalid."""

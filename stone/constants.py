"""Project-wide constants."""

from enum import StrEnum


class Board(StrEnum):
    """Supported board identifiers."""

    SH_MAIN = "sh_main"
    SZ_MAIN = "sz_main"
    CHINEXT = "chinext"
    STAR = "star"
    BSE = "bse"


class FactorCategory(StrEnum):
    """High-level factor categories."""

    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MONEYFLOW = "moneyflow"
    THEME = "theme"


KLINE_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]
MIN_HISTORY_DAYS = 250
AKSHARE_MAX_RATE = 3.0

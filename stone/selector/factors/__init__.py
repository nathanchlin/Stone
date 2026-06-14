"""Factor registry."""

from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stone.selector.factors.base import Factor

REGISTRY: dict[str, type["Factor"]] = {}


def register_factor(cls: type["Factor"]) -> type["Factor"]:
    """Register a factor class by its unique name."""
    name = getattr(cls, "name", None)
    if not isinstance(name, str) or not name:
        raise ValueError(f"Factor {cls} must define a non-empty string `name`")
    if name in REGISTRY:
        raise ValueError(f"Factor `{name}` is already registered")
    REGISTRY[name] = cls
    return cls


with suppress(Exception):  # pragma: no cover - import side effect only
    from stone.selector.factors import fundamental, moneyflow, technical, theme  # noqa: F401

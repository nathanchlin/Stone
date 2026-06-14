# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

🚧 **Design phase.** Only scaffolding exists (`pyproject.toml`, `main.py`, `stone/__init__.py`, `tests/conftest.py`). All real implementation is yet to come from the two design docs in `docs/superpowers/`:

- **Spec:** `docs/superpowers/specs/2026-06-14-a-stock-selector-design.md` — requirements, architecture, data layer, factor taxonomy, constraints
- **Plan:** `docs/superpowers/plans/2026-06-14-stock-selector-implementation.md` — 30-task TDD breakdown (Setup → Phase 1 Data → Phase 2 Selector → Wrap-up)

Read both before non-trivial work. The plan uses `- [ ]` checkboxes per task — tick them as you complete steps.

## Legal Boundary (Hard Constraint)

This is a **personal investment research assistant**, not advisory software. The README and spec §1.2 define red lines that must be respected in any change:

- **Never** implement: stock recommendations (荐股), automated order placement, or price prediction
- **Allowed**: candidate screening by user-preset conditions, multi-factor scoring by user-preset weights, position arithmetic on user-preset rules, stop-loss/take-profit monitoring, strategy backtesting

When adding features, ask: "Is the user making the decision, or is the code?" If the code is deciding what to buy/sell, stop.

## Common Commands

Package manager is **uv** (not pip). Python 3.12.

```bash
# Setup
uv sync                         # Install all deps (incl. dev) from uv.lock
uv sync --extra dev             # Explicit dev install
uv run stone <cmd>              # Run the CLI (entry: stone.cli:app)
python main.py <cmd>            # Equivalent — main.py just delegates

# Test (coverage ≥ 80% is enforced via --cov-fail-under=80)
uv run pytest                   # Full suite
uv run pytest tests/unit/factors/test_technical.py::test_rsi     # Single test
uv run pytest -k "rsi and not integration"                       # By name pattern
uv run pytest -m "not integration"                               # Skip slow
uv run pytest --no-cov          # Skip coverage (faster iteration)

# Lint / types
uv run ruff check .             # Lint (rules: E F W I N UP B SIM; line-length 100; E501 ignored)
uv run ruff check --fix .       # Auto-fix
uv run ruff format .            # Format
uv run mypy stone               # Type check (non-strict, ignore_missing_imports)

# Build
uv build                        # Wheel via hatchling
```

Test markers registered: `integration`, `e2e`. Use them to scope slow/network tests.

## Architecture

Layered, **single-direction dependencies** (upper calls lower, never reverse). This invariant is critical — `selector` must not import `reporters`, etc.

```
CLI (stone.cli)  →  selector.engine (pipeline)
                        │
                        ├── selector.factors.*   (16 factors: pure functions, registered in REGISTRY)
                        ├── selector.strategy    (YAML → pydantic)
                        ├── selector.scoring     (weighted average over self-history percentile)
                        ├── selector.constraints (industry diversification)
                        └── selector.position_sizing (arithmetic on user rules)
                                │
                                ▼
                    data.* (the foundation — future phases 3/4/5 depend on this)
                        ├── fetchers/akshare_fetcher.py  (rate-limited ≤3 req/s, tenacity retry)
                        ├── cache/parquet_store.py        (partitioned by date×code)
                        ├── universe.py                   (board + ST + delisting filters)
                        ├── incremental.py                (T-day delta)
                        └── quality.py                    (completeness self-check)
```

**Why the data layer matters most:** Phases 3 (monitoring), 4 (backtest), 5 (portfolio) all build on `data/`. Its interfaces stabilize first.

**Factor design rule:** A factor is a pure function `data → scalar score`. No side effects, no I/O — this makes them composable and unit-testable.

**Config is data, not code:** strategies live in `config/strategies/*.yaml` (pydantic-validated). Code parses, never hard-codes strategy logic.

## Key Directories (Planned)

- `config/strategies/` — versioned strategy YAMLs (`band_trend_v1`, `breakout_strong`, `value_with_catalyst`)
- `config/personal/` — **gitignored** real-money position rules; only `.example.yaml` templates are committed
- `data_cache/`, `reports/`, `logs/` — all **gitignored** runtime artifacts (parquet cache, output reports, run logs)
- `tests/{unit,integration,e2e}/` — split by scope; `tests/helpers/` holds kline generators and seed data
- `tests/conftest.py` provides `tmp_data_cache` fixture for cache-related tests

## Conventions

- **Naming:** Spec uses top-level `data/`, `selector/`, `reporters/`; implementation uses `stone/data/`, etc. — the `stone.` prefix avoids stdlib collisions (see plan "Naming convention note"). New code follows the `stone/` prefix.
- **TDD:** Plan enforces RED → GREEN → REFACTOR → COMMIT per task. Write failing test first.
- **Comments / docs:** Project README and design docs are in Chinese; code identifiers and docstrings are in English. Match surrounding style.
- **Coverage gate:** PRs will not pass CI below 80% (`--cov-fail-under=80` in `pyproject.toml`).

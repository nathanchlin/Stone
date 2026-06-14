# Stone Setup Guide

## One-time setup

```bash
# 1. Clone
git clone https://github.com/nathanchlin/Stone.git
cd Stone

# 2. Install dependencies (requires uv: brew install uv)
uv sync --all-extras

# 3. Initial data backfill (this takes 30-60 minutes for full market)
uv run python main.py update --backfill 2024-01-01 2026-06-14

# 4. Personal position rules (private)
cp config/position_rules.example.yaml config/personal/position_rules.yaml
# Edit config/personal/position_rules.yaml with your real capital

# 5. Test selection manually
uv run python main.py select --strategy band_trend_v1

# 6. (Optional) Schedule daily run
cp launchd/com.stone.daily.plist ~/Library/LaunchAgents/
# Edit the plist: replace YOUR_USERNAME with your actual username
launchctl load ~/Library/LaunchAgents/com.stone.daily.plist
```

## Daily usage

After launchd is configured, reports will be generated automatically at 16:00 each weekday.
View them in `reports/`.

## Manual override

```bash
# Rerun today's selection
uv run python main.py select --strategy band_trend_v1

# Retry failed data updates
uv run python main.py update --retry-failed

# Run all strategies
uv run python main.py select --all-strategies
```

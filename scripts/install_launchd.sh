#!/usr/bin/env bash
# Install the 3 daily analysis launchd jobs (8:30 pre-market, 14:00 intraday, 16:00 review).
# Usage: bash scripts/install_launchd.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHD_SRC="$PROJECT_DIR/launchd"
LAUNCHD_DST="$HOME/Library/LaunchAgents"
JOBS=(com.stone.pre-market com.stone.intraday com.stone.review)

mkdir -p "$LAUNCHD_DST"
mkdir -p "$PROJECT_DIR/logs"

echo "[setup] project: $PROJECT_DIR"
echo "[setup] launchd dst: $LAUNCHD_DST"
echo ""

# Verify plist paths point to current user's home
USER_HOME="$HOME"
if ! grep -q "$USER_HOME/Stone" "$LAUNCHD_SRC/${JOBS[0]}.plist" 2>/dev/null; then
    echo "[warn] plist paths don't match current \$HOME ($USER_HOME)"
    echo "[warn] edit launchd/*.plist to point to your project path before installing"
    exit 1
fi

for job in "${JOBS[@]}"; do
    src="$LAUNCHD_SRC/$job.plist"
    dst="$LAUNCHD_DST/$job.plist"

    if launchctl list 2>/dev/null | grep -q "$job"; then
        echo "[unload] $job (already loaded)"
        launchctl unload "$dst" 2>/dev/null || true
    fi

    cp "$src" "$dst"
    launchctl load "$dst"
    echo "[load]   $job → $dst"
done

echo ""
echo "[done] 3 jobs installed. Verify with:"
echo "  launchctl list | grep com.stone"
echo ""
echo "Run manually to test:"
echo "  uv run python scripts/daily_analysis.py --mode pre-market"
echo "  uv run python scripts/daily_analysis.py --mode intraday"
echo "  uv run python scripts/daily_analysis.py --mode review"
echo ""
echo "Uninstall:"
echo "  bash scripts/uninstall_launchd.sh"

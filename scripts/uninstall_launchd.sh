#!/usr/bin/env bash
# Uninstall the 3 daily analysis launchd jobs.

set -euo pipefail

LAUNCHD_DST="$HOME/Library/LaunchAgents"
JOBS=(com.stone.pre-market com.stone.intraday com.stone.review)

for job in "${JOBS[@]}"; do
    dst="$LAUNCHD_DST/$job.plist"
    if [ -f "$dst" ]; then
        launchctl unload "$dst" 2>/dev/null || true
        rm -f "$dst"
        echo "[removed] $dst"
    else
        echo "[skip]    $dst (not installed)"
    fi
done

echo ""
echo "[done] all 3 jobs uninstalled"

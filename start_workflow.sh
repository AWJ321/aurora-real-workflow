#!/bin/bash
set -e

WORKFLOW_BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
export WORKFLOW_BASE_DIR
CYLC_WORKFLOW_DIR="$WORKFLOW_BASE_DIR/aurora_real"
GIF_DIR="/data/projects/17001770/weather_department/nwp/wjang/aurora_real/data/plots/gif"

echo "=============================="
echo " Aurora Workflow Starter"
echo " Workflow dir: $WORKFLOW_BASE_DIR"
echo " Time: $(date -u)"
echo "=============================="

source /app/apps/miniforge3/25.3.1/etc/profile.d/conda.sh
conda activate aurora_env
export LD_PRELOAD=$CONDA_PREFIX/lib/libstdc++.so.6

echo ""
echo "Detecting latest available ECMWF data..."
LATEST_AVAILABLE=$(timeout 180 python $WORKFLOW_BASE_DIR/scripts/detect_start.py 2>/dev/null)
if [ -z "$LATEST_AVAILABLE" ]; then
    echo "WARNING: Could not detect latest available data, will use last GIF + 6h"
else
    echo "Latest available: $LATEST_AVAILABLE"
fi

LATEST_GIF=$(ls $GIF_DIR/aurora_forecast_*.gif 2>/dev/null | sort | tail -1)

if [ -z "$LATEST_GIF" ]; then
    if [ -z "$LATEST_AVAILABLE" ]; then
        echo "ERROR: No GIFs found and could not detect latest available. Exiting."
        exit 1
    fi
    echo ""
    echo "No existing GIFs found — starting fresh from $LATEST_AVAILABLE"
    START_FROM=$LATEST_AVAILABLE
else
    BASENAME=$(basename $LATEST_GIF .gif)
    DATE_PART=$(echo $BASENAME | sed 's/aurora_forecast_//')
    DATE=$(echo $DATE_PART | cut -d'_' -f1 | tr -d '-')
    HOUR=$(echo $DATE_PART | cut -d'_' -f2)
    LAST_COMPLETED="${DATE}T${HOUR}00Z"

    echo ""
    echo "Last completed cycle: $LAST_COMPLETED"

    NEXT_EPOCH=$(date -u -d "${DATE:0:4}-${DATE:4:2}-${DATE:6:2}T${HOUR}:00:00Z + 6 hours" +%s)
    START_FROM=$(date -u -d "@$NEXT_EPOCH" +"%Y%m%dT%H%MZ")
    echo "Starting from: $START_FROM"
fi

echo ""
echo "Cleaning previous workflow run..."
cylc stop --now --now aurora_real/run1 2>/dev/null || true
sleep 3
cylc clean aurora_real --yes 2>/dev/null || true
rm -f /data/projects/17001770/weather_department/nwp/wjang/aurora_real/caught_up.txt

echo ""
echo "Installing workflow..."
cylc install $CYLC_WORKFLOW_DIR

echo ""
echo "Starting workflow from $START_FROM ..."
cylc play aurora_real --initial-cycle-point $START_FROM

echo ""
echo "=============================="
echo " Workflow started successfully"
echo " Monitor with: cylc tui aurora_real"
echo " Latest available : $LATEST_AVAILABLE"
echo " Starting from    : $START_FROM"
echo "=============================="

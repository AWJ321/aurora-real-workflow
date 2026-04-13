#!/bin/bash
# ==============================================================================
# Aurora Real-Time Workflow Starter
# Usage: bash start_workflow.sh
# ==============================================================================

set -e

# Load config values
WORKFLOW_BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
source /home/app/apps/miniforge3/24.3.0/etc/profile.d/conda.sh
conda activate aurora_env
export LD_PRELOAD=$CONDA_PREFIX/lib/libstdc++.so.6
export WORKFLOW_BASE_DIR

CYLC_WORKFLOW_DIR="$WORKFLOW_BASE_DIR/aurora_real"

echo "=============================="
echo " Aurora Workflow Starter"
echo " Workflow dir: $WORKFLOW_BASE_DIR"
echo " Time: $(date -u)"
echo "=============================="

# Detect latest available cycle point
echo ""
echo "Detecting latest available ECMWF data..."
CYCLE_POINT=$(python $WORKFLOW_BASE_DIR/scripts/detect_start.py 2>/dev/null)

if [ -z "$CYCLE_POINT" ]; then
    echo "ERROR: Could not detect latest available data. Exiting."
    exit 1
fi

echo "Latest available cycle point: $CYCLE_POINT"

# Clean any previous run
echo ""
echo "Cleaning previous workflow run..."
cylc clean aurora_real --yes 2>/dev/null || true

# Install workflow
echo ""
echo "Installing workflow..."
cylc install $CYLC_WORKFLOW_DIR

# Play workflow from detected cycle point
echo ""
echo "Starting workflow from $CYCLE_POINT ..."
cylc play aurora_real --initial-cycle-point $CYCLE_POINT

echo ""
echo "=============================="
echo " Workflow started successfully"
echo " Monitor with: cylc tui aurora_real"
echo "=============================="

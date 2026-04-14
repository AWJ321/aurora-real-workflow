#!/bin/bash
#PBS -N aurora_wait_adaptive
#PBS -P 17001770
#PBS -l select=1:ncpus=1:mem=1gb
#PBS -l walltime=10:00:00
#PBS -j oe
#PBS -q normal
#PBS -o /data/projects/17001770/weather_department/nwp/wjang/aurora_real/logs/wait_adaptive.log

DURATION_FILE="/data/projects/17001770/weather_department/nwp/wjang/aurora_real/data_availability_duration.txt"
LEEWAY_SECS=1800   # 30 minutes

echo "=============================="
echo " Aurora Adaptive Wait Started"
echo " Host: $(hostname)"
echo " Time: $(date -u)"
echo "=============================="

# Read duration from file written by cycle 3 download
if [ ! -f "$DURATION_FILE" ]; then
    echo "WARNING: Duration file not found: $DURATION_FILE"
    echo "Falling back to default 5.5h sleep"
    SLEEP_SECS=19800
else
    DURATION_SECS=$(cat "$DURATION_FILE" | head -1 | tr -d '[:space:]')
    SLEEP_SECS=$((DURATION_SECS - LEEWAY_SECS))

    # Safety check — never sleep less than 0
    if [ "$SLEEP_SECS" -lt 0 ]; then
        SLEEP_SECS=0
    fi

    DURATION_HRS=$((DURATION_SECS / 3600))
    DURATION_MINS=$(( (DURATION_SECS % 3600) / 60 ))
    SLEEP_HRS=$((SLEEP_SECS / 3600))
    SLEEP_MINS=$(( (SLEEP_SECS % 3600) / 60 ))

    echo ""
    echo " Data availability duration (from cycle 3): ${DURATION_HRS}h ${DURATION_MINS}m"
    echo " Sleeping for                             : ${SLEEP_HRS}h ${SLEEP_MINS}m (duration - 30 min)"
    WAKE_TIME=$(date -u -d "+${SLEEP_SECS} seconds" "+%Y-%m-%d %H:%M UTC" 2>/dev/null || date -u -r $(($(date +%s) + SLEEP_SECS)) "+%Y-%m-%d %H:%M UTC")
    echo " Will start probing at                    : $WAKE_TIME"
    echo ""
fi

echo "=============================="
echo " Sleeping for ${SLEEP_SECS} seconds..."
echo "=============================="

sleep $SLEEP_SECS

echo "=============================="
echo " Aurora Adaptive Wait Finished"
echo " Time: $(date -u)"
echo "=============================="

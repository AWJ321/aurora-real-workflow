#!/bin/bash
#PBS -N aurora_wait_adaptive
#PBS -P 17001770
#PBS -l select=1:ncpus=1:mem=1gb
#PBS -l walltime=10:00:00
#PBS -j oe
#PBS -q normal
#PBS -o /data/projects/17001770/weather_department/nwp/wjang/aurora_real/logs/wait_adaptive.log

DURATION_FILE="/data/projects/17001770/weather_department/nwp/wjang/aurora_real/data_availability_duration.txt"
CAUGHT_UP_FILE="/data/projects/17001770/weather_department/nwp/wjang/aurora_real/caught_up.txt"
LEEWAY_SECS=1800

echo "=============================="
echo " Aurora Adaptive Wait Started"
echo " Host: $(hostname)"
echo " Time: $(date -u)"
echo " Cycle point: $CYLC_TASK_CYCLE_POINT"
echo "=============================="

# Check if still catching up — if so skip sleep entirely
if [ ! -f "$CAUGHT_UP_FILE" ]; then
    echo ""
    echo " Catch-up mode — skipping sleep, running immediately"
    echo ""
    echo "=============================="
    echo " Aurora Adaptive Wait Finished"
    echo " Time: $(date -u)"
    echo "=============================="
    exit 0
fi

# Check if this is new Cycle 2 or 3 (caught_up + 6h or 12h) — no sleep needed
CAUGHT_UP=$(cat "$CAUGHT_UP_FILE")
CAUGHT_UP_DATE="${CAUGHT_UP:0:4}-${CAUGHT_UP:4:2}-${CAUGHT_UP:6:2}"
CAUGHT_UP_HOUR="${CAUGHT_UP:9:2}"
CAUGHT_UP_EPOCH=$(date -u -d "${CAUGHT_UP_DATE}T${CAUGHT_UP_HOUR}:00:00Z" +%s)

CYCLE_DATE="${CYLC_TASK_CYCLE_POINT:0:4}-${CYLC_TASK_CYCLE_POINT:4:2}-${CYLC_TASK_CYCLE_POINT:6:2}"
CYCLE_HOUR="${CYLC_TASK_CYCLE_POINT:9:2}"
CYCLE_EPOCH=$(date -u -d "${CYCLE_DATE}T${CYCLE_HOUR}:00:00Z" +%s)

DIFF=$(( CYCLE_EPOCH - CAUGHT_UP_EPOCH ))

if [ "$DIFF" -lt 64800 ]; then
    echo ""
    echo " New Cycle 2 or 3 ($(( DIFF/3600 ))h after caught-up cycle) — no sleep needed"
    echo ""
    echo "=============================="
    echo " Aurora Adaptive Wait Finished"
    echo " Time: $(date -u)"
    echo "=============================="
    exit 0
fi

# Normal operation — new Cycle 4+, sleep based on measured duration
if [ ! -f "$DURATION_FILE" ]; then
    echo "WARNING: Duration file not found, falling back to 5.5h sleep"
    SLEEP_SECS=19800
else
    DURATION_SECS=$(cat "$DURATION_FILE" | head -1 | tr -d '[:space:]')
    SLEEP_SECS=$((DURATION_SECS - LEEWAY_SECS))

    if [ "$SLEEP_SECS" -lt 0 ]; then
        SLEEP_SECS=0
    fi

    DURATION_HRS=$((DURATION_SECS / 3600))
    DURATION_MINS=$(( (DURATION_SECS % 3600) / 60 ))
    SLEEP_HRS=$((SLEEP_SECS / 3600))
    SLEEP_MINS=$(( (SLEEP_SECS % 3600) / 60 ))

    echo ""
    echo " New Cycle 4+ — normal adaptive wait"
    echo " Data availability duration (from cycle 3): ${DURATION_HRS}h ${DURATION_MINS}m"
    echo " Sleeping for                             : ${SLEEP_HRS}h ${SLEEP_MINS}m (duration - 30 min)"
    WAKE_TIME=$(date -u -d "+${SLEEP_SECS} seconds" "+%Y-%m-%d %H:%M UTC" 2>/dev/null)
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

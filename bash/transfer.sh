#!/bin/bash
#PBS -N aurora_transfer
#PBS -P 17001770
#PBS -l select=1:ncpus=1:mem=4gb
#PBS -l walltime=00:30:00
#PBS -j oe
#PBS -q normal
#PBS -o /home/users/gov/nea/ang.wj/scratch/aurora_real/logs/transfer.log

REMOTE="aramanathan@118.189.84.226"
REMOTE_BASE="/nas44/aramanathan/AI-NWP/RealTime/aurora"
LOCAL_BASE="/home/users/gov/nea/ang.wj/scratch/aurora_real/data"

CYCLE_POINT=$CYLC_TASK_CYCLE_POINT
CYCLE_DATE="${CYCLE_POINT:0:4}-${CYCLE_POINT:4:2}-${CYCLE_POINT:6:2}"
CYCLE_HOUR="${CYCLE_POINT:9:2}"
INIT_STR="${CYCLE_DATE}_${CYCLE_HOUR}"

echo "=============================="
echo " Aurora Transfer Started"
echo " Host: $(hostname)"
echo " Time: $(date)"
echo " Cycle: $INIT_STR"
echo "=============================="

# Main forecast plots
rsync -av $LOCAL_BASE/plots/gif/aurora_forecast_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/plots/gif/ 2>/dev/null || echo "No GIF found for $INIT_STR"
rsync -av $LOCAL_BASE/plots/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/plots/frames/${INIT_STR}/ 2>/dev/null || echo "No frames found for $INIT_STR"

# Precip plots
rsync -av $LOCAL_BASE/plots_precip/gif/aurora_precip_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/plots_precip/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_precip/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/plots_precip/frames/${INIT_STR}/ 2>/dev/null || true

# Wind plots
rsync -av $LOCAL_BASE/plots_wind/gif/aurora_wind925hPa_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/plots_wind/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/gif/aurora_wind850hPa_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/plots_wind/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/gif/aurora_wind700hPa_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/plots_wind/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/frames/925hPa/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/plots_wind/frames/925hPa/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/frames/850hPa/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/plots_wind/frames/850hPa/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/frames/700hPa/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/plots_wind/frames/700hPa/${INIT_STR}/ 2>/dev/null || true

# Comparison (main)
rsync -av $LOCAL_BASE/comparison/gif/comparison_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/comparison/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/comparison/frames/${INIT_STR}/ 2>/dev/null || true

# Comparison panels — precip
rsync -av $LOCAL_BASE/comparison/precip/gif/comparison_precip_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/comparison/precip/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/precip/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/comparison/precip/frames/${INIT_STR}/ 2>/dev/null || true

# Comparison panels — wind
rsync -av $LOCAL_BASE/comparison/wind_925/gif/comparison_wind925hPa_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/comparison/wind_925/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/wind_925/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/comparison/wind_925/frames/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/wind_850/gif/comparison_wind850hPa_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/comparison/wind_850/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/wind_850/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/comparison/wind_850/frames/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/wind_700/gif/comparison_wind700hPa_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/comparison/wind_700/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/wind_700/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/comparison/wind_700/frames/${INIT_STR}/ 2>/dev/null || true

# Recent — clear remote and rsync fresh
echo "Updating recent/..."
ssh $REMOTE "rm -rf $REMOTE_BASE/comparison/recent && mkdir -p $REMOTE_BASE/comparison/recent"
rsync -av $LOCAL_BASE/comparison/recent/ \
    $REMOTE:$REMOTE_BASE/comparison/recent/ 2>/dev/null || echo "No recent files to transfer"
ssh $REMOTE "chmod -R o+r $REMOTE_BASE/comparison/recent && chmod o+rx $REMOTE_BASE/comparison/recent"

echo "=============================="
echo " Aurora Transfer Finished"
echo " Time: $(date)"
echo "=============================="

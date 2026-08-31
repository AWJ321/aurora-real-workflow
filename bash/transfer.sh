#!/bin/bash
#PBS -N aurora_transfer
#PBS -P 17001770
#PBS -l select=1:ncpus=1:mem=4gb
#PBS -l walltime=00:30:00
#PBS -j oe
#PBS -q normal
#PBS -o /data/projects/17001770/weather_department/nwp/wjang/aurora_real/logs/transfer.log

REMOTE="aramanathan@118.189.84.226"
REMOTE_BASE="/nas44/aramanathan/AI-NWP/RealTime/aurora"
LOCAL_BASE="/data/projects/17001770/weather_department/nwp/wjang/aurora_real/data"

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

rsync -av $LOCAL_BASE/plots/gif/aurora_forecast_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/plots/gif/ 2>/dev/null || echo "No GIF found for $INIT_STR"

rsync -av $LOCAL_BASE/plots/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/plots/frames/${INIT_STR}/ 2>/dev/null || echo "No frames found for $INIT_STR"

rsync -av $LOCAL_BASE/plots_precip/gif/aurora_precip_${INIT_STR}.gif     $REMOTE:$REMOTE_BASE/plots_precip/gif/ 2>/dev/null || echo "No precip GIF found for $INIT_STR"
rsync -av $LOCAL_BASE/plots_precip/frames/${INIT_STR}/     $REMOTE:$REMOTE_BASE/plots_precip/frames/${INIT_STR}/ 2>/dev/null || echo "No precip frames found for $INIT_STR"
rsync -av $LOCAL_BASE/plots_wind/gif/aurora_wind925hPa_${INIT_STR}.gif     $REMOTE:$REMOTE_BASE/plots_wind/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/gif/aurora_wind850hPa_${INIT_STR}.gif     $REMOTE:$REMOTE_BASE/plots_wind/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/gif/aurora_wind700hPa_${INIT_STR}.gif     $REMOTE:$REMOTE_BASE/plots_wind/gif/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/frames/925hPa/${INIT_STR}/     $REMOTE:$REMOTE_BASE/plots_wind/frames/925hPa/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/frames/850hPa/${INIT_STR}/     $REMOTE:$REMOTE_BASE/plots_wind/frames/850hPa/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/plots_wind/frames/700hPa/${INIT_STR}/     $REMOTE:$REMOTE_BASE/plots_wind/frames/700hPa/${INIT_STR}/ 2>/dev/null || true
rsync -av $LOCAL_BASE/comparison/gif/comparison_${INIT_STR}.gif \
    $REMOTE:$REMOTE_BASE/comparison/gif/ 2>/dev/null || echo "No comparison GIF found for $INIT_STR"

rsync -av $LOCAL_BASE/comparison/frames/${INIT_STR}/ \
    $REMOTE:$REMOTE_BASE/comparison/frames/${INIT_STR}/ 2>/dev/null || echo "No comparison frames found for $INIT_STR"

# --- Copy latest comparison frames to /recent, renamed as 01.png, 02.png, ... ---
echo "Copying latest comparison frames to recent/..."
RECENT_DEST="$REMOTE_BASE/comparison/recent"

LATEST_FOLDER=$(ssh $REMOTE "ls -d $REMOTE_BASE/comparison/frames/????-??-??_?? 2>/dev/null | sort | tail -1")

if [ -z "$LATEST_FOLDER" ]; then
    echo "No comparison frame folders found on remote — skipping recent copy"
else
    echo "Latest folder: $LATEST_FOLDER"
    ssh $REMOTE "
        mkdir -p $RECENT_DEST

        # Clear out any stale files from previous runs
        rm -f $RECENT_DEST/*.png $RECENT_DEST/*.gif

        counter=1
        for f in \$(ls $LATEST_FOLDER/comparison_*-lead-*.png 2>/dev/null | sort); do
            [ -f \"\$f\" ] || continue
            newname=\$(printf '%02d.png' \$counter)
            cp \"\$f\" \"$RECENT_DEST/\$newname\"
            counter=\$((counter + 1))
        done
        echo \"Done copying \$(ls $RECENT_DEST/*.png 2>/dev/null | wc -l) frame files to $RECENT_DEST\"
    "
fi

# --- Copy latest comparison GIF to /recent, renamed as animation.gif ---
LATEST_GIF=$(ssh $REMOTE "ls $REMOTE_BASE/comparison/gif/comparison_*.gif 2>/dev/null | sort | tail -1")

if [ -z "$LATEST_GIF" ]; then
    echo "No comparison GIF found on remote — skipping"
else
    echo "Latest GIF: $LATEST_GIF"
    ssh $REMOTE "
        cp \"$LATEST_GIF\" \"$RECENT_DEST/animation.gif\"

        # Fix permissions so files are readable by others (e.g. web server)
        chmod -R o+r $RECENT_DEST
        chmod o+rx $RECENT_DEST
    "
    echo "Copied as animation.gif and fixed permissions"
fi

echo "=============================="
echo " Aurora Transfer Finished"
echo " Time: $(date)"
echo "=============================="
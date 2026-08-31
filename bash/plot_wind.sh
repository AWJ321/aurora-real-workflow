#!/bin/bash
#PBS -N aurora_plot_wind
#PBS -P 17001770
#PBS -l select=1:ncpus=1:mem=32gb
#PBS -l walltime=02:00:00
#PBS -j oe
#PBS -q normal
#PBS -o /data/projects/17001770/weather_department/nwp/wjang/aurora_real/logs/plot_wind.log

echo "=============================="
echo " Aurora Wind Plot Started"
echo " Host: $(hostname)"
echo " Time: $(date)"
echo "=============================="

source /app/apps/miniforge3/25.3.1/etc/profile.d/conda.sh
conda activate aurora_env
export LD_PRELOAD=$CONDA_PREFIX/lib/libstdc++.so.6

/home/users/gov/nea/ang.wj/.conda/envs/aurora_env/bin/python ${WORKFLOW_BASE_DIR}/scripts/plot_wind.py

EXIT_CODE=$?
echo "=============================="
echo " Aurora Wind Plot Finished"
echo " Exit code: $EXIT_CODE"
echo " Time: $(date)"
echo "=============================="
exit $EXIT_CODE

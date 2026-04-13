#!/bin/bash
#PBS -N aurora_inference
#PBS -P 17001770
#PBS -l select=1:ncpus=8:ngpus=1:mem=64gb
#PBS -l walltime=04:00:00
#PBS -j oe
#PBS -o /data/projects/17001770/weather_department/nwp/wjang/aurora_real/logs/inference.log

echo "=============================="
echo " Aurora Inference Started"
echo " Host: $(hostname)"
echo " Time: $(date)"
echo "=============================="

source /app/apps/miniforge3/25.3.1/etc/profile.d/conda.sh
conda activate aurora_env
export LD_PRELOAD=$CONDA_PREFIX/lib/libstdc++.so.6

python ${WORKFLOW_BASE_DIR}/scripts/inference.py

EXIT_CODE=$?

echo "=============================="
echo " Aurora Inference Finished"
echo " Exit code: $EXIT_CODE"
echo " Time: $(date)"
echo "=============================="

exit $EXIT_CODE

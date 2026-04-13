#!/bin/bash
#PBS -N aurora_plot
#PBS -P 17001770
#PBS -l select=1:ncpus=4:mem=32gb
#PBS -l walltime=01:00:00
#PBS -j oe
#PBS -o ${WORKFLOW_BASE_DIR}/logs/plot.log

echo "=============================="
echo " Aurora Plot Started"
echo " Host: $(hostname)"
echo " Time: $(date)"
echo "=============================="

source /home/app/apps/miniforge3/24.3.0/etc/profile.d/conda.sh
conda activate aurora_env
export LD_PRELOAD=$CONDA_PREFIX/lib/libstdc++.so.6

python ${WORKFLOW_BASE_DIR}/scripts/plot.py

EXIT_CODE=$?

echo "=============================="
echo " Aurora Plot Finished"
echo " Exit code: $EXIT_CODE"
echo " Time: $(date)"
echo "=============================="

exit $EXIT_CODE

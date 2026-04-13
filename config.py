# ==============================================================================
# Aurora Real-Time Workflow Configuration
# Edit this file before running the workflow on a new system.
# ==============================================================================

import os

# ------------------------------------------------------------------------------
# USER SETTINGS — edit these for your system
# ------------------------------------------------------------------------------

# Your username on the cluster
USER = "ang.wj"

# Base directory where all data will be stored
BASE_DIR = "/data/projects/17001770/weather_department/nwp/wjang/aurora_real"

# PBS project code
PBS_PROJECT = "17001770"

# Cylc platform name (check with your HPC admin if unsure)
PLATFORM = "aspire"

# Home directory where workflow scripts live
WORKFLOW_DIR = os.path.join(os.path.expanduser("~"), "aurora_real_workflow")

# ------------------------------------------------------------------------------
# DERIVED PATHS — do not edit these
# ------------------------------------------------------------------------------

# Data directories
RAW_SFC_DIR  = os.path.join(BASE_DIR, "data", "raw", "sfc")
RAW_PL_DIR   = os.path.join(BASE_DIR, "data", "raw", "pl")
MERGED_DIR   = os.path.join(BASE_DIR, "data", "merged")
FORECAST_DIR = os.path.join(BASE_DIR, "data", "forecasts")
PRECIP_DIR   = os.path.join(BASE_DIR, "data", "precip")
PLOTS_DIR    = os.path.join(BASE_DIR, "data", "plots")

# Model and config files
MODEL_CKPT   = os.path.join(BASE_DIR, "model", "aurora-0.1-finetuned.ckpt")
COEFF_CSV    = os.path.join(BASE_DIR, "config", "fit_coefficients.csv")

# Log directory
LOG_DIR      = os.path.join(BASE_DIR, "logs")

# ------------------------------------------------------------------------------
# DOWNLOAD SETTINGS — adjust if needed
# ------------------------------------------------------------------------------
RETRY_INTERVAL_MINS  = 10
CYCLE2_TIMEOUT_HOURS = 7
STEADY_TIMEOUT_HOURS = 2

# ------------------------------------------------------------------------------
# FORECAST SETTINGS
# ------------------------------------------------------------------------------
FORECAST_HOURS = 168
STEP_HOURS     = 6

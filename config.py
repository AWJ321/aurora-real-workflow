# ==============================================================================
# Aurora Real-Time Workflow Configuration
# Edit this file before running the workflow on a new system.
# ==============================================================================

import os

# ------------------------------------------------------------------------------
# USER SETTINGS — edit these for your system
# ------------------------------------------------------------------------------

USER = "ang.wj"

BASE_DIR = "/data/projects/17001770/weather_department/nwp/wjang/aurora_real"

PBS_PROJECT = "17001770"

PLATFORM = "aspire"

WORKFLOW_DIR = os.path.join(os.path.expanduser("~"), "aurora_real_workflow")

# ------------------------------------------------------------------------------
# DERIVED PATHS — do not edit these
# ------------------------------------------------------------------------------

RAW_SFC_DIR  = os.path.join(BASE_DIR, "data", "raw", "sfc")
RAW_PL_DIR   = os.path.join(BASE_DIR, "data", "raw", "pl")
MERGED_DIR   = os.path.join(BASE_DIR, "data", "merged")
FORECAST_DIR = os.path.join(BASE_DIR, "data", "forecasts")
PRECIP_DIR   = os.path.join(BASE_DIR, "data", "precip")
PLOTS_DIR        = os.path.join(BASE_DIR, "data", "plots")
PLOTS_GIF_DIR    = os.path.join(PLOTS_DIR, "gif")
PLOTS_FRAMES_DIR = os.path.join(PLOTS_DIR, "frames")

MODEL_CKPT   = os.path.join(BASE_DIR, "model", "aurora-0.1-finetuned.ckpt")
COEFF_CSV    = os.path.join(BASE_DIR, "config", "fit_coefficients.csv")

LOG_DIR      = os.path.join(BASE_DIR, "logs")

DURATION_FILE = os.path.join(BASE_DIR, "data_availability_duration.txt")

# AIFS frames directory — for comparison plots
AIFS_FRAMES_DIR = "/data/projects/17001770/weather_department/nwp/wjang/aifs_rt/data/plots/frames"

# Comparison output directory
COMPARISON_DIR = os.path.join(BASE_DIR, "data", "comparison")

# ------------------------------------------------------------------------------
# DOWNLOAD SETTINGS
# ------------------------------------------------------------------------------
RETRY_INTERVAL_MINS  = 10
CYCLE2_TIMEOUT_HOURS = 7
STEADY_TIMEOUT_HOURS = 2

# ------------------------------------------------------------------------------
# FORECAST SETTINGS
# ------------------------------------------------------------------------------
FORECAST_HOURS = 168
STEP_HOURS     = 6

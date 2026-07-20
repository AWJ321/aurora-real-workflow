import os

USER = "ang.wj"
BASE_DIR = "/data/projects/17001770/weather_department/nwp/wjang/aurora_real"
PBS_PROJECT = "17001770"
PLATFORM = "aspire"

RAW_SFC_DIR  = os.path.join(BASE_DIR, "data", "raw", "sfc")
RAW_PL_DIR   = os.path.join(BASE_DIR, "data", "raw", "pl")
MERGED_DIR   = os.path.join(BASE_DIR, "data", "merged")
FORECAST_DIR = os.path.join(BASE_DIR, "data", "forecasts")
PRECIP_DIR   = os.path.join(BASE_DIR, "data", "precip")
PLOTS_DIR        = os.path.join(BASE_DIR, "data", "plots")
PLOTS_GIF_DIR    = os.path.join(PLOTS_DIR, "gif")
PLOTS_FRAMES_DIR = os.path.join(PLOTS_DIR, "frames")
COMPARISON_DIR        = os.path.join(BASE_DIR, "data", "comparison")
COMPARISON_GIF_DIR    = os.path.join(COMPARISON_DIR, "gif")
COMPARISON_FRAMES_DIR = os.path.join(COMPARISON_DIR, "frames")

MODEL_CKPT = "/data/projects/17001770/weather_department/nwp/wjang/aurora_real/model/aurora-0.1-finetuned.ckpt"
COEFF_CSV  = "/data/projects/17001770/weather_department/nwp/wjang/aurora_real/fit_coefficients.csv"

LOG_DIR        = os.path.join(BASE_DIR, "logs")
DURATION_FILE  = os.path.join(BASE_DIR, "data_availability_duration.txt")
CAUGHT_UP_FILE = os.path.join(BASE_DIR, "caught_up.txt")

AIFS_FRAMES_DIR = "/data/projects/17001770/weather_department/nwp/wjang/aifs_rt/data/plots/frames"

RETRY_INTERVAL_MINS  = 10
CYCLE2_TIMEOUT_HOURS = 7
STEADY_TIMEOUT_HOURS = 4
FORECAST_HOURS = 168
STEP_HOURS     = 6

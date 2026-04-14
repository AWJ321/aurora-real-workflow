# Aurora Real-Time Workflow

Real-time AI weather forecasting pipeline running on HPC cluster using Cylc 8 and PBS.

Every 6 hours:
1. Downloads latest ECMWF atmospheric data from MARS
2. Runs Aurora AI model for 7-day forecast
3. Derives precipitation using regression parameterisation
4. Generates animated GIF of SE Asia weather forecast

---

## Repository Structure

    aurora-real-workflow/
    |-- aurora_real/
    |   |-- flow.cylc              # Cylc workflow scheduling
    |-- scripts/
    |   |-- config.py              # All configuration — edit this first
    |   |-- detect_start.py        # Detects latest available ECMWF cycle
    |   |-- download.py            # Downloads ECMWF MARS data
    |   |-- inference.py           # Runs Aurora model inference
    |   |-- derive_precip.py       # Derives precipitation from forecast
    |   |-- plot.py                # Generates forecast GIF animation
    |-- bash/
    |   |-- download.sh
    |   |-- inference.sh
    |   |-- derive_precip.sh
    |   |-- plot.sh
    |-- start_workflow.sh          # Main entry point
    |-- fit_coefficients.csv       # Precipitation regression coefficients
    |-- config.py                  # All paths and settings — edit this first

---

## Prerequisites

- Access to ECMWF MARS API (requires .ecmwfapirc credentials file)
- Cylc 8.5+ 
- PBS job scheduler
- Conda/Miniforge

---

## Setup

### 1. Clone the repository into your storage directory

    cd /data/projects/17001770/weather_department/nwp/wjang
    git clone https://github.com/AWJ321/aurora-real-workflow.git aurora_real
    cd aurora_real

### 2. Edit config.py

Open config.py and update:

    USER = "your_username"
    BASE_DIR = "/data/projects/17001770/weather_department/nwp/wjang/aurora_real"
    PBS_PROJECT = "17001770"
    PLATFORM = "aspire"

### 3. Create data directories

    source /app/apps/miniforge3/25.3.1/etc/profile.d/conda.sh
    conda activate aurora_env
    python -c "
    import sys; sys.path.insert(0, '/data/projects/17001770/weather_department/nwp/wjang/aurora_real')
    import config, os
    for d in [config.RAW_SFC_DIR, config.RAW_PL_DIR, config.MERGED_DIR,
              config.FORECAST_DIR, config.PRECIP_DIR, config.PLOTS_DIR,
              config.LOG_DIR, os.path.dirname(config.MODEL_CKPT),
              os.path.dirname(config.COEFF_CSV)]:
        os.makedirs(d, exist_ok=True)
        print(f'Created: {d}')
    "

### 4. Copy fit_coefficients.csv to config directory

    cp fit_coefficients.csv /data/projects/17001770/weather_department/nwp/wjang/aurora_real/config/

### 5. Download Aurora model checkpoint (~4.5GB)

    wget -O /data/projects/17001770/weather_department/nwp/wjang/aurora_real/model/aurora-0.1-finetuned.ckpt https://huggingface.co/microsoft/aurora/resolve/main/aurora-0.1-finetuned.ckpt

### 6. Set up ECMWF API credentials

Create ~/.ecmwfapirc:

    {
      "url": "https://api.ecmwf.int/v1",
      "key": "YOUR_API_KEY",
      "email": "YOUR_EMAIL"
    }

### 7. Create conda environment and install packages

    source /app/apps/miniforge3/25.3.1/etc/profile.d/conda.sh
    conda create -n aurora_env python=3.10 -y
    conda activate aurora_env
    pip install cylc-flow
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
    pip install microsoft-aurora
    pip install ecmwf-api-client
    pip install xarray cfgrib netCDF4 scipy numpy pandas
    pip install metpy cartopy matplotlib imageio tqdm
    pip install huggingface_hub

### 8. Set up Cylc platform configuration

Create ~/.cylc/flow/global.cylc:

    mkdir -p ~/.cylc/flow
    cat > ~/.cylc/flow/global.cylc << EOF
    [platforms]
        [[aspire]]
            hosts = localhost
            job runner = pbs
            install target = localhost
            cylc path = /home/users/gov/nea/YOUR_USERNAME/.conda/envs/aurora_env/bin
    EOF

Replace YOUR_USERNAME with your actual username.

---

## Running the Workflow

    bash /data/projects/17001770/weather_department/nwp/wjang/aurora_real/start_workflow.sh

### Monitor

    cylc tui aurora_real
    qstat -u your_username

### Stop

    cylc stop --kill aurora_real

### Clean and restart

    cylc stop --kill aurora_real
    cylc clean aurora_real --yes
    bash start_workflow.sh

---

## Scheduling Logic

Cycle 1  — Starts immediately, data already confirmed available by detect_start.py
Cycle 2  — Starts immediately after Cycle 1 finishes, probes MARS every 10 min for up to 7h
Cycle 3+ — Waits 5.5h after previous cycle finishes (tiny sleep job), then probes every 10 min for 2h

---

## Output

Animated GIF files saved to:

    {BASE_DIR}/data/plots/aurora_forecast_YYYY-MM-DD_HH.gif

Download to local machine:

    scp your_username@aspire2a.nscc.sg:/data/projects/17001770/weather_department/nwp/wjang/aurora_real/data/plots/*.gif C:\Users\your_username\Desktop\

---

## PBS Resources

    Task          CPUs   GPUs   RAM     Walltime   Queue
    download       2      0      8gb     8h         normal
    inference      8      1     64gb     4h         ai
    derive_precip  4      0     32gb     1h         normal
    plot           4      0     32gb     1h         normal
    wait_5h30m     1      0      1gb     6h         normal

---

## Troubleshooting

Check logs:

    find ~/cylc-run/aurora_real -name "job.out" | sort
    cat ~/cylc-run/aurora_real/run1/log/job/CYCLE_POINT/TASK/01/job.out


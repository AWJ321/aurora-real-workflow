# Aurora Real-Time Workflow

Real-time AI weather forecasting pipeline running on HPC cluster using Cylc 8 and PBS.

Every 6 hours:
1. Downloads latest ECMWF atmospheric data from MARS
2. Runs Aurora AI model for 7-day forecast
3. Derives precipitation using MLP regression parameterisation
4. Generates animated GIF and individual PNG frames of SE Asia weather forecast
5. Generates side-by-side Aurora vs AIFS comparison plots
6. Transfers outputs to remote server

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
    |   |-- derive_precip.py       # Derives precipitation using MLP
    |   |-- plot.py                # Generates forecast GIF and PNG frames
    |   |-- plot_comparison.py     # Generates Aurora vs AIFS comparison plots
    |-- bash/
    |   |-- download.sh
    |   |-- inference.sh
    |   |-- derive_precip.sh
    |   |-- plot.sh
    |   |-- plot_comparison.sh
    |   |-- wait_adaptive.sh
    |   |-- transfer.sh
    |-- start_workflow.sh          # Main entry point
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
              config.PLOTS_GIF_DIR, config.PLOTS_FRAMES_DIR,
              config.LOG_DIR, os.path.dirname(config.MODEL_CKPT),
              config.MLP_MODEL_DIR]:
        os.makedirs(d, exist_ok=True)
        print(f'Created: {d}')
    "

### 4. Download Aurora model checkpoint (~4.5GB)

    wget -O /data/projects/17001770/weather_department/nwp/wjang/aurora_real/model/aurora-0.1-finetuned.ckpt https://huggingface.co/microsoft/aurora/resolve/main/aurora-0.1-finetuned.ckpt

### 5. Copy MLP precipitation model files

Copy the following files to model/mlp/:

    mlp_model_NE.pt
    mlp_model_SW.pt
    mlp_model_IM.pt
    mlp_scaler_NE.pkl
    mlp_scaler_SW.pkl
    mlp_scaler_IM.pkl

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
    pip install Pillow

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

### 9. Set up SSH key for remote transfer

    ssh-keygen -t rsa -b 4096
    ssh-copy-id aramanathan@118.189.84.226

---

## Running the Workflow

    bash /data/projects/17001770/weather_department/nwp/wjang/aurora_real/start_workflow.sh

### Monitor

    cylc tui aurora_real
    qstat -u your_username

### Stop

    cylc stop --kill aurora_real

---

## After System Maintenance / Server Restart

The workflow does not restart automatically after maintenance. To restart manually:

### 1. Restart the workflow

    conda activate aurora_env
    bash /data/projects/17001770/weather_department/nwp/wjang/aurora_real/start_workflow.sh

start_workflow.sh automatically:
- Finds the last completed cycle from data/plots/gif/
- Starts from that cycle + 6h to catch up all missed cycles
- Runs missed cycles back to back with no waiting
- Resumes normal operation once caught up to latest available data

### 2. Monitor catch-up progress

    cylc tui aurora_real

### 3. Verify catch-up completed

    cat /data/projects/17001770/weather_department/nwp/wjang/aurora_real/caught_up.txt

---

## Scheduling Logic

Catch-up cycles — if missed cycles exist, runs all back to back immediately with no waiting
New Cycle 1   — latest available data, downloads immediately
New Cycle 2   — starts immediately after Cycle 1, probes MARS every 10 min for up to 7h
New Cycle 3   — starts immediately after Cycle 2, probes every 10 min for up to 7h, records data availability duration
New Cycle 4+  — wait_adaptive checks if data already available, skips sleep if so; otherwise sleeps (measured duration - 30 min), then probes every 10 min for up to 4h

Data availability duration is measured dynamically in new Cycle 3 and saved to data_availability_duration.txt
Only written if caught_up.txt exists — ensures catch-up cycles never corrupt the measurement

---

## Output

    data/plots/
    |-- gif/
    |   |-- aurora_forecast_YYYY-MM-DD_HH.gif
    |-- frames/
    |   |-- YYYY-MM-DD_HH/
    |       |-- aurora_forecast_YYYY-MM-DD_HH-lead-006h.png
    |       |-- ... (28 files)
    data/comparison/
    |-- gif/
    |   |-- comparison_YYYY-MM-DD_HH.gif
    |-- frames/
        |-- YYYY-MM-DD_HH/
            |-- comparison_YYYY-MM-DD_HH-lead-006h.png
            |-- ... (28 files)

---

## PBS Resources

    Task             CPUs   GPUs   RAM     Walltime   Queue   Retries
    download          1      0      8gb     8h         normal  10
    inference         1      1     64gb     4h         ai      10
    derive_precip     1      0     32gb     1h         normal  10
    plot              1      0     32gb     1h         normal  10
    plot_comparison   1      0     32gb     1h         normal  10
    transfer          1      0      4gb     30min      normal  10
    wait_adaptive     1      0      1gb     10h        normal  —

---

## Troubleshooting

Check logs:

    find ~/cylc-run/aurora_real -name "job.out" | sort
    cat ~/cylc-run/aurora_real/run1/log/job/CYCLE_POINT/TASK/01/job.out

Common issues:
- Missing merged GRIB: download failed, check download log
- Model checkpoint not found: re-run wget command in step 4
- MLP model files not found: copy mlp_model_*.pt and mlp_scaler_*.pkl to model/mlp/
- CYLC_WORKFLOW_INITIAL_CYCLE_POINT not set: fallback used, workflow still runs correctly
- PBS queue wait times for GPU nodes can be long, forecasts may drift behind real time
- Never run start_workflow.sh multiple times without stopping the previous run first
- If caught_up.txt exists from a previous run, start_workflow.sh deletes it automatically
- ECMWF API token expires periodically — update ~/.ecmwfapirc with new key when downloads fail with authentication error
- MARS queue can be very slow during peak periods — download jobs will retry automatically
- SSH key for transfer needs to be re-added after Aspire2A maintenance: ssh-copy-id aramanathan@118.189.84.226

#!/usr/bin/env python3
"""
Run Aurora inference for a single forecast initialization.
Reads 2 consecutive merged GRIB files, runs 28-step rollout (7 days),
and saves 28 NetCDF forecast files.
"""

import os
import sys
import warnings
import pickle
from datetime import datetime, timedelta
import numpy as np
import torch
import xarray as xr
from aurora import AuroraHighRes, Batch, Metadata, rollout
from huggingface_hub import hf_hub_download

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ==============================================================================
# CONFIGURATION — all settings come from config.py
# ==============================================================================
FORECAST_HOURS = config.FORECAST_HOURS
STEP_HOURS     = config.STEP_HOURS
N_STEPS        = FORECAST_HOURS // STEP_HOURS
MERGED_DIR     = config.MERGED_DIR
FORECAST_DIR   = config.FORECAST_DIR
MODEL_CKPT     = config.MODEL_CKPT
# ==============================================================================

os.makedirs(FORECAST_DIR, exist_ok=True)


def get_cycle_time():
    cycle_point = os.environ.get("CYLC_TASK_CYCLE_POINT")
    if cycle_point:
        try:
            dt = datetime.strptime(cycle_point, "%Y%m%dT%H%MZ")
            print(f"Cycle time from Cylc: {dt}")
            return dt
        except ValueError:
            print(f"WARNING: Could not parse CYLC_TASK_CYCLE_POINT='{cycle_point}'")
    INIT_TIME = datetime(2026, 4, 7, 6)
    print(f"Using manual INIT_TIME: {INIT_TIME}")
    return INIT_TIME


def timestamp_str(dt):
    return dt.strftime("%Y-%m-%d_%H")


def fix_coordinates(ds):
    lon_values = ds.longitude.values.astype(np.float32)
    new_lons = np.mod(lon_values, 360)
    new_lons[new_lons == 360] = 0.0
    ds = ds.assign_coords(longitude=new_lons)
    ds = ds.sortby("longitude")
    return ds


def lon_360_to_180(lon):
    lon = lon.copy()
    lon[lon > 180] -= 360
    return lon


def load_grib(fpath):
    print(f"  Loading SFC from {os.path.basename(fpath)} ...")
    sfc_ds = xr.load_dataset(
        fpath, engine="cfgrib",
        filter_by_keys={"typeOfLevel": "surface"},
        decode_timedelta=True,
    )
    print(f"  Loading PL from {os.path.basename(fpath)} ...")
    pl_ds = xr.load_dataset(
        fpath, engine="cfgrib",
        filter_by_keys={"typeOfLevel": "isobaricInhPa"},
        decode_timedelta=True,
    )
    sfc_ds = fix_coordinates(sfc_ds)
    pl_ds  = fix_coordinates(pl_ds)
    return sfc_ds, pl_ds


def validate_datasets(sfc_ds, pl_ds, ts):
    required_sfc = ["t2m", "u10", "v10", "msl"]
    missing_sfc = [v for v in required_sfc if v not in sfc_ds.data_vars]
    if missing_sfc:
        raise ValueError(f"[{ts}] Missing surface vars: {missing_sfc}")
    required_pl = ["t", "u", "v", "q", "z"]
    missing_pl = [v for v in required_pl if v not in pl_ds.data_vars]
    if missing_pl:
        raise ValueError(f"[{ts}] Missing pressure-level vars: {missing_pl}")
    levels = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]
    available = set(pl_ds.isobaricInhPa.values.tolist())
    missing_levels = [l for l in levels if l not in available]
    if missing_levels:
        raise ValueError(f"[{ts}] Missing pressure levels: {missing_levels}")
    print(f"  ✓ Validation passed for {ts}")


def build_batch(sfc_t0, pl_t0, sfc_t1, pl_t1, static_vars, init_time):
    levels = np.array([1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50])

    def rename_sfc(ds):
        return ds.rename({"t2m": "2t", "u10": "10u", "v10": "10v"})

    sfc_t0 = rename_sfc(sfc_t0)
    sfc_t1 = rename_sfc(sfc_t1)

    surf_vars = {
        v: torch.from_numpy(
            np.stack([sfc_t0[v].values, sfc_t1[v].values])[None]
        ).float()
        for v in ["2t", "10u", "10v", "msl"]
    }

    atmos_vars = {
        v: torch.from_numpy(
            np.stack([
                pl_t0[v].sel(isobaricInhPa=list(levels)).values,
                pl_t1[v].sel(isobaricInhPa=list(levels)).values,
            ])[None]
        ).float()
        for v in ["t", "u", "v", "q", "z"]
    }

    metadata = Metadata(
        lat=torch.from_numpy(pl_t1.latitude.values.astype(np.float32)),
        lon=torch.from_numpy(pl_t1.longitude.values.astype(np.float32)),
        time=(init_time,),
        atmos_levels=levels,
    )

    batch = Batch(
        surf_vars=surf_vars,
        static_vars={k: torch.from_numpy(v).float() for k, v in static_vars.items()},
        atmos_vars=atmos_vars,
        metadata=metadata,
    )

    return batch, levels


def save_forecast_step(batch_step, step_idx, init_time, levels, forecast_dir):
    lead_hours = step_idx * STEP_HOURS
    step_time  = np.datetime64(init_time) + np.timedelta64(lead_hours, "h")
    lat = batch_step.metadata.lat.cpu().numpy()
    lon = lon_360_to_180(batch_step.metadata.lon.cpu().numpy())

    atm_data = {
        v: (("isobaricInhPa", "latitude", "longitude"),
            np.squeeze(t.cpu().numpy()).astype(np.float32))
        for v, t in batch_step.atmos_vars.items()
    }
    surf_data = {
        v: (("latitude", "longitude"),
            np.squeeze(t.cpu().numpy()).astype(np.float32))
        for v, t in batch_step.surf_vars.items()
    }
    static_data = {}
    for v, t in batch_step.static_vars.items():
        var_name = "z_sfc" if v == "z" else v
        static_data[var_name] = (
            ("latitude", "longitude"),
            t.cpu().numpy().astype(np.float32)
        )

    ds = xr.Dataset(
        data_vars={**atm_data, **surf_data, **static_data},
        coords={
            "time":          ("time", [step_time]),
            "valid_time":    ("time", [step_time]),
            "isobaricInhPa": ("isobaricInhPa", levels),
            "latitude":      ("latitude", lat),
            "longitude":     ("longitude", lon),
        },
    )

    init_str = init_time.strftime("%Y-%m-%d_%H")
    out_name = f"aurora_forecast_{init_str}-out-{lead_hours}.nc"
    out_path = os.path.join(forecast_dir, out_name)
    ds.to_netcdf(out_path)
    print(f"  ✓ Saved: {out_name}")
    return out_path


def main():
    INIT_TIME = get_cycle_time()

    print("=" * 60)
    print(" Aurora Inference Script")
    print(f" Init time : {INIT_TIME}")
    print(f" Steps     : {N_STEPS} × {STEP_HOURS}h = {FORECAST_HOURS}h forecast")
    print("=" * 60)

    t0_time = INIT_TIME - timedelta(hours=STEP_HOURS)
    t1_time = INIT_TIME
    t0_str  = timestamp_str(t0_time)
    t1_str  = timestamp_str(t1_time)

    t0_grib = os.path.join(MERGED_DIR, f"aurora_merged_{t0_str}.grib")
    t1_grib = os.path.join(MERGED_DIR, f"aurora_merged_{t1_str}.grib")

    for f in [t0_grib, t1_grib]:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Missing merged GRIB: {f}\nRun download.py first.")

    init_str = INIT_TIME.strftime("%Y-%m-%d_%H")
    expected = {f"aurora_forecast_{init_str}-out-{s*STEP_HOURS}.nc" for s in range(1, N_STEPS+1)}
    if expected.issubset(set(os.listdir(FORECAST_DIR))):
        print(f"All {N_STEPS} forecast steps already exist, skipping.")
        return

    print("\nLoading static variables ...")
    static_path = hf_hub_download(repo_id="microsoft/aurora", filename="aurora-0.1-static.pickle")
    with open(static_path, "rb") as f:
        static_vars = pickle.load(f)
    print("✓ Static variables loaded")

    print("\nLoading model checkpoint ...")
    if not os.path.exists(MODEL_CKPT):
        raise FileNotFoundError(
            f"Model checkpoint not found: {MODEL_CKPT}\n"
            f"Download with:\n"
            f"  wget -O {MODEL_CKPT} "
            f"https://huggingface.co/microsoft/aurora/resolve/main/aurora-0.1-finetuned.ckpt"
        )

    model = AuroraHighRes()
    model.load_checkpoint_local(MODEL_CKPT)
    model.eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"✓ Model loaded | Device: {device}")

    print(f"\nLoading t0: {t0_str}")
    sfc_t0, pl_t0 = load_grib(t0_grib)
    validate_datasets(sfc_t0, pl_t0, t0_str)

    print(f"\nLoading t1: {t1_str}")
    sfc_t1, pl_t1 = load_grib(t1_grib)
    validate_datasets(sfc_t1, pl_t1, t1_str)

    print("\nBuilding input batch ...")
    batch, levels = build_batch(sfc_t0, pl_t0, sfc_t1, pl_t1, static_vars, INIT_TIME)
    batch = batch.to(device)
    print("✓ Batch ready")

    print(f"\nRunning {N_STEPS}-step rollout ...")
    preds = []
    with torch.inference_mode():
        for step, p in enumerate(rollout(model, batch, steps=N_STEPS), start=1):
            p = p.to("cpu")
            preds.append(p)
            torch.cuda.empty_cache()
            print(f"  Step {step:02d}/{N_STEPS} done")

    print(f"✓ Rollout complete — {len(preds)} steps")

    print(f"\nSaving {N_STEPS} forecast files ...")
    for step_idx, batch_step in enumerate(preds, start=1):
        save_forecast_step(batch_step, step_idx, INIT_TIME, levels, FORECAST_DIR)

    print("\n" + "=" * 60)
    print(f" Inference complete! {len(preds)} files saved to:")
    print(f" {FORECAST_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Derive precipitation from Aurora forecast variables using curve-fit coefficients.
"""

import os
import sys
import glob
import numpy as np
import xarray as xr
import pandas as pd
from scipy.ndimage import gaussian_filter
import metpy.calc as mpcalc
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ==============================================================================
# CONFIGURATION — all settings come from config.py
# ==============================================================================
FORECAST_DIR = config.FORECAST_DIR
PRECIP_DIR   = config.PRECIP_DIR
COEFF_CSV    = config.COEFF_CSV
# ==============================================================================

EPS             = 0.1
SMOOTHING_SIGMA = 1

LOW_LEVEL   = 850
UPPER_LEVEL = 200
WIND_LEVEL  = 700

PREDICTORS = [
    "CONV_850",
    "DIV_200",
    "q_850",
    "T_850",
    "WSPD_700",
    "CONV850_x_q850",
]

os.makedirs(PRECIP_DIR, exist_ok=True)


def load_coeffs(coeff_csv, predictors):
    df     = pd.read_csv(coeff_csv).set_index("predictor")
    coeffs = df["coeff_train"]
    vec    = np.array([coeffs["intercept"]] + [coeffs[p] for p in predictors])
    print("Coefficients loaded:")
    for name, val in zip(["intercept"] + predictors, vec):
        print(f"  {name:25s}: {val:+.6e}")
    return vec


def standardize(ds):
    return ds.rename({k: v for k, v in
                      {"latitude": "lat", "longitude": "lon"}.items()
                      if k in ds.coords})


def normalize_lon(ds):
    if "lon" not in ds.coords:
        return ds
    if ds.lon.values.max() > 180:
        ds = ds.assign_coords(lon=(ds.lon.values + 180) % 360 - 180)
        ds = ds.sortby("lon")
    return ds


def squeeze_time(ds):
    if "time" in ds.dims:
        ds = ds.isel(time=0, drop=True)
    return ds.drop_vars(["time", "valid_time"], errors="ignore")


def sm(arr, lat, lon):
    dlat = abs(float(lat[1] - lat[0]))
    dlon = abs(float(lon[1] - lon[0]))
    SMOOTH_DEG = SMOOTHING_SIGMA * 0.25
    sigma_lat  = SMOOTH_DEG / dlat
    sigma_lon  = SMOOTH_DEG / dlon
    return gaussian_filter(arr, sigma=[sigma_lat, sigma_lon]).astype(np.float32)


def divergence_np(u, v, lat, lon):
    u_da = xr.DataArray(u.astype(float),
                        coords={"lat": lat, "lon": lon}, dims=["lat", "lon"])
    v_da = xr.DataArray(v.astype(float),
                        coords={"lat": lat, "lon": lon}, dims=["lat", "lon"])
    div  = mpcalc.divergence(u_da.metpy.quantify(), v_da.metpy.quantify())
    return np.array(div.metpy.dequantify(), dtype=np.float32)


def sel_level(ds, var, level):
    da = ds[var]
    if "time" in da.dims:
        da = da.isel(time=0, drop=True)
    for dim in da.dims:
        if dim in ("lat", "lon", "latitude", "longitude"):
            continue
        return da.sel({dim: level}).squeeze().values.astype(np.float32)
    return da.squeeze().values.astype(np.float32)


def get_uv(ds, level):
    u = sel_level(ds, "u", level)
    v = sel_level(ds, "v", level)
    return u, v


def compute_precip(ds, coeff_vec, predictors):
    ds  = standardize(ds)
    ds  = normalize_lon(ds)
    ds  = squeeze_time(ds)

    lat = ds.lat.values
    lon = ds.lon.values

    u850, v850 = get_uv(ds, LOW_LEVEL)
    conv850    = sm(-divergence_np(u850, v850, lat, lon), lat, lon)

    u200, v200 = get_uv(ds, UPPER_LEVEL)
    div200     = sm(divergence_np(u200, v200, lat, lon), lat, lon)

    q850 = sel_level(ds, "q", LOW_LEVEL)
    t850 = sel_level(ds, "t", LOW_LEVEL)

    try:
        u700, v700 = get_uv(ds, WIND_LEVEL)
        wspd700    = sm(np.sqrt(u700**2 + v700**2).astype(np.float32), lat, lon)
    except Exception as e:
        print(f"  WARN: 700hPa wind failed ({e}) — filling zeros")
        wspd700 = np.zeros_like(q850)

    preds = {
        "CONV_850":       conv850,
        "DIV_200":        div200,
        "q_850":          q850,
        "T_850":          t850,
        "WSPD_700":       wspd700,
        "CONV850_x_q850": conv850 * q850,
    }

    n    = len(lat) * len(lon)
    X    = np.column_stack(
        [np.ones(n, dtype=np.float64)] +
        [preds[p].ravel().astype(np.float64) for p in predictors]
    )
    pred = np.clip(np.exp(X @ coeff_vec) - EPS, 0, None)
    pred = pred.reshape(len(lat), len(lon)).astype(np.float32)

    return pred, lat, lon


def main():
    print("=" * 60)
    print(" Aurora Derive Precipitation Script")
    print(f" Input  : {FORECAST_DIR}")
    print(f" Output : {PRECIP_DIR}")
    print("=" * 60)

    coeff_vec = load_coeffs(COEFF_CSV, PREDICTORS)
    print()

    all_files = sorted(glob.glob(os.path.join(FORECAST_DIR, "aurora_forecast_*.nc")))
    if not all_files:
        raise FileNotFoundError(f"No forecast files found in {FORECAST_DIR}")

    todo = []
    for fpath in all_files:
        fname      = os.path.basename(fpath)
        out_fname  = fname.replace("aurora_forecast_", "aurora_precip_")
        out_path   = os.path.join(PRECIP_DIR, out_fname)
        if not os.path.exists(out_path):
            todo.append((fpath, out_path))

    if not todo:
        print("All precip files already derived, nothing to do.")
        return

    print(f"Found {len(all_files)} forecast files, {len(todo)} need processing.\n")

    failed = []
    for fpath, out_path in tqdm(todo, desc="Deriving precip"):
        fname = os.path.basename(fpath)
        try:
            ds = xr.open_dataset(fpath)
            pred, lat, lon = compute_precip(ds, coeff_vec, PREDICTORS)
            ds.close()

            ds_out = xr.Dataset(
                {"precip_mm": (("latitude", "longitude"), pred)},
                coords={
                    "latitude":  ("latitude",  lat),
                    "longitude": ("longitude", lon),
                },
                attrs={"description": "Derived precipitation from Aurora curve-fit parameterisation"}
            )
            ds_out.to_netcdf(out_path)
            ds_out.close()

        except Exception as e:
            print(f"  ✗ Failed {fname}: {e}")
            failed.append(fname)

    print("\n" + "=" * 60)
    print(f" Derive precip complete!")
    print(f" Success : {len(todo) - len(failed)}/{len(todo)} files")
    if failed:
        print(f" Failed  : {failed}")
    print(f" Output  : {PRECIP_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

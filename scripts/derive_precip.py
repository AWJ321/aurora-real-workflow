#!/usr/bin/env python3
"""
derive_precip.py — MLP-based precipitation derivation for Aurora real-time workflow.
Reads all 28 forecast NetCDF files for the current Cylc cycle point,
derives precipitation using season-specific MLP models, saves to PRECIP_DIR.
"""

import os
import sys
import pickle
import warnings
import numpy as np
import xarray as xr
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime, timedelta
from scipy.ndimage import gaussian_filter
import metpy.calc as mpcalc
from metpy.units import units as munits

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ==============================================================================
# CONFIGURATION
# ==============================================================================
FORECAST_DIR   = Path(config.FORECAST_DIR)
PRECIP_DIR     = Path(config.PRECIP_DIR)
MLP_MODEL_DIR  = Path(config.MLP_MODEL_DIR)

DOMAIN         = {"lat_min": -12, "lat_max": 23, "lon_min": 92, "lon_max": 127}
LOW_LEVEL      = 850
UPPER_LEVEL    = 200
WIND_LEVEL     = 700
MID_LEVEL      = 500
PREDICTORS     = [
    "CONV_850", "DIV_200", "q_850", "T_850", "WSPD_700",
    "CONV850_x_q850", "TEND_CONV850_6h", "TEND_CONV850_12h", "TEND_q850_6h",
    "RH_700", "lapse_rate", "WSPD_850", "VORT_850", "WSPD_200", "DIV_500",
]
EPS            = 0.1
SMOOTHING_SIGMA = 1
VAR_MAP        = {"u": ["u", "u10", "ua"], "v": ["v", "v10", "va"]}
DEVICE         = torch.device("cpu")  # CPU only in workflow

SEASONS = {
    "NE": [11, 12, 1, 2, 3],
    "SW": [6, 7, 8, 9],
    "IM": [4, 5, 10],
}
# ==============================================================================


class PrecipMLP(nn.Module):
    def __init__(self, n_features):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 256), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(256, 128),        nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, 64),         nn.ReLU(),
            nn.Linear(64, 1),
        )
    def forward(self, x):
        return self.net(x).squeeze(-1)


def get_season(month):
    for name, months in SEASONS.items():
        if month in months:
            return name
    return "IM"


model_cache  = {}
scaler_cache = {}


def load_model(month):
    season = get_season(month)
    if season not in model_cache:
        model = PrecipMLP(len(PREDICTORS)).to(DEVICE)
        model.load_state_dict(torch.load(
            MLP_MODEL_DIR / f"mlp_model_{season}.pt", map_location=DEVICE))
        model.eval()
        model_cache[season] = model
        with open(MLP_MODEL_DIR / f"mlp_scaler_{season}.pkl", "rb") as f:
            scaler_cache[season] = pickle.load(f)
        print(f"  Model loaded for season: {season}")
    return model_cache[season], scaler_cache[season]


def get_cycle_time():
    cp = os.environ.get("CYLC_TASK_CYCLE_POINT")
    if cp:
        return datetime.strptime(cp, "%Y%m%dT%H%MZ")
    raise RuntimeError("CYLC_TASK_CYCLE_POINT not set")


def make_nc_path(init_time, lead):
    return FORECAST_DIR / f"aurora_forecast_{init_time.strftime('%Y-%m-%d_%H')}-out-{lead}.nc"


def make_precip_path(init_time, lead):
    return PRECIP_DIR / f"aurora_precip_{init_time.strftime('%Y-%m-%d_%H')}-out-{lead}.nc"


def open_nc(fpath):
    try:
        return xr.open_dataset(str(fpath), engine="netcdf4")
    except Exception:
        return xr.open_dataset(str(fpath), engine="scipy")


def standardize(ds):
    rename = {k: v for k, v in {"latitude": "lat", "longitude": "lon"}.items() if k in ds.coords}
    return ds.rename(rename) if rename else ds


def normalize_lon(ds):
    if "lon" not in ds.coords:
        return ds
    if ds.lon.values.max() > 180:
        ds = ds.assign_coords(lon=(ds.lon.values + 180) % 360 - 180)
        ds = ds.sortby("lon")
    return ds


def clip_domain(ds):
    lats = ds["lat"].values
    if lats[0] > lats[-1]:
        return ds.sel(lat=slice(DOMAIN["lat_max"], DOMAIN["lat_min"]),
                      lon=slice(DOMAIN["lon_min"],  DOMAIN["lon_max"]))
    return ds.sel(lat=slice(DOMAIN["lat_min"], DOMAIN["lat_max"]),
                  lon=slice(DOMAIN["lon_min"], DOMAIN["lon_max"]))


def prepare(ds):
    ds = standardize(ds)
    ds = normalize_lon(ds)
    ds = clip_domain(ds)
    if "time" in ds.dims:
        ds = ds.isel(time=0, drop=True)
    return ds


def sm(arr, lat, lon):
    dlat = abs(float(lat[1] - lat[0]))
    dlon = abs(float(lon[1] - lon[0]))
    smooth_deg = SMOOTHING_SIGMA * 0.25
    return gaussian_filter(arr, sigma=[smooth_deg / dlat, smooth_deg / dlon]).astype(np.float32)


def divergence_2d(u_arr, v_arr, lat, lon):
    u_da = xr.DataArray(u_arr.astype(float), coords={"lat": lat, "lon": lon}, dims=["lat", "lon"])
    v_da = xr.DataArray(v_arr.astype(float), coords={"lat": lat, "lon": lon}, dims=["lat", "lon"])
    div  = mpcalc.divergence(u_da.metpy.quantify(), v_da.metpy.quantify())
    return np.array(div.metpy.dequantify(), dtype=np.float32)


def vorticity_2d(u_arr, v_arr, lat, lon):
    R = 6371000.0
    dlat = np.deg2rad(np.abs(lat[1] - lat[0]))
    dlon = np.deg2rad(np.abs(lon[1] - lon[0]))
    dy = R * dlat
    lat_rad = np.deg2rad(lat)
    dx = R * np.cos(lat_rad) * dlon
    dvdx = np.gradient(v_arr, axis=1) / dx[:, None]
    dudy = np.gradient(u_arr, axis=0) / dy
    return (dvdx - dudy).astype(np.float32)


def sel_level(ds, var_name, level):
    da = ds[var_name]
    for dim in da.dims:
        if dim in ("lat", "lon"):
            continue
        da = da.sel({dim: level})
    return da.squeeze().values.astype(np.float32)


def get_uv_level(ds, level):
    def extract(aliases):
        for name in aliases:
            if name not in ds:
                continue
            da = ds[name]
            for dim in da.dims:
                if dim in ("lat", "lon"):
                    continue
                da = da.sel({dim: level})
                break
            return da.squeeze().values.astype(np.float32)
        raise KeyError(f"wind not found at level {level}")
    return extract(VAR_MAP["u"]), extract(VAR_MAP["v"])


def get_q850(ds):
    if "q" in ds:
        return sel_level(ds, "q", LOW_LEVEL)
    elif "r" in ds:
        t_arr = sel_level(ds, "t", LOW_LEVEL)
        r_arr = sel_level(ds, "r", LOW_LEVEL)
        if r_arr.max() > 1.5:
            r_arr = r_arr / 100.0
        t_K   = t_arr * munits.kelvin
        rh_fr = r_arr * munits.dimensionless
        w_s   = mpcalc.saturation_mixing_ratio(LOW_LEVEL * 100.0 * munits.pascal, t_K)
        q_arr = mpcalc.specific_humidity_from_mixing_ratio(rh_fr * w_s)
        return np.array(q_arr.to("kg/kg").magnitude, dtype=np.float32)
    raise KeyError("Neither q nor r found")


def get_rh700(ds):
    if "q" in ds:
        q700 = sel_level(ds, "q", WIND_LEVEL)
        t700 = sel_level(ds, "t", WIND_LEVEL)
        rh = mpcalc.relative_humidity_from_specific_humidity(
            WIND_LEVEL * 100 * munits.pascal,
            t700 * munits.kelvin,
            q700 * munits("kg/kg"),
        )
        return (rh.to("dimensionless").magnitude * 100).astype(np.float32)
    elif "r" in ds:
        r700 = sel_level(ds, "r", WIND_LEVEL)
        return r700 if r700.max() > 1.5 else r700 * 100.0
    return None


def compute_conv850_q850(fpath, lat, lon):
    ds = prepare(open_nc(fpath))
    u850, v850 = get_uv_level(ds, LOW_LEVEL)
    conv850 = sm(-divergence_2d(u850, v850, lat, lon), lat, lon)
    q850    = get_q850(ds)
    ds.close()
    return conv850, q850


def derive_one(fpath, init_time, lead, model, scaler):
    ds  = prepare(open_nc(fpath))
    lat = ds.lat.values
    lon = ds.lon.values

    u850, v850 = get_uv_level(ds, LOW_LEVEL)
    conv850    = sm(-divergence_2d(u850, v850, lat, lon), lat, lon)
    wspd850    = sm(np.sqrt(u850**2 + v850**2).astype(np.float32), lat, lon)
    vort850    = sm(vorticity_2d(u850, v850, lat, lon), lat, lon)

    u200, v200 = get_uv_level(ds, UPPER_LEVEL)
    div200     = sm(divergence_2d(u200, v200, lat, lon), lat, lon)
    wspd200    = sm(np.sqrt(u200**2 + v200**2).astype(np.float32), lat, lon)

    try:
        u700, v700 = get_uv_level(ds, WIND_LEVEL)
        wspd700    = sm(np.sqrt(u700**2 + v700**2).astype(np.float32), lat, lon)
    except Exception:
        wspd700 = np.zeros_like(conv850)

    try:
        u500, v500 = get_uv_level(ds, MID_LEVEL)
        div500     = sm(divergence_2d(u500, v500, lat, lon), lat, lon)
    except Exception:
        div500 = np.zeros_like(conv850)

    t850       = sel_level(ds, "t", LOW_LEVEL)
    t500       = sel_level(ds, "t", MID_LEVEL)
    q850       = get_q850(ds)
    lapse_rate = t850 - t500

    rh700 = get_rh700(ds)
    if rh700 is None:
        rh700 = np.zeros_like(conv850)

    ds.close()

    # Tendency predictors
    path_tm6 = make_nc_path(init_time, lead - 6)
    if lead >= 6 and path_tm6.exists():
        try:
            conv850_tm6, q850_tm6 = compute_conv850_q850(path_tm6, lat, lon)
            tend_conv850_6h = conv850 - conv850_tm6
            tend_q850_6h    = q850   - q850_tm6
        except Exception:
            tend_conv850_6h = np.zeros_like(conv850)
            tend_q850_6h    = np.zeros_like(q850)
    else:
        tend_conv850_6h = np.zeros_like(conv850)
        tend_q850_6h    = np.zeros_like(q850)

    path_tm12 = make_nc_path(init_time, lead - 12)
    if lead >= 12 and path_tm12.exists():
        try:
            conv850_tm12, _ = compute_conv850_q850(path_tm12, lat, lon)
            tend_conv850_12h = conv850 - conv850_tm12
        except Exception:
            tend_conv850_12h = np.zeros_like(conv850)
    else:
        tend_conv850_12h = np.zeros_like(conv850)

    preds = {
        "CONV_850":          conv850,
        "DIV_200":           div200,
        "q_850":             q850,
        "T_850":             t850,
        "WSPD_700":          wspd700,
        "CONV850_x_q850":    conv850 * q850,
        "TEND_CONV850_6h":   tend_conv850_6h,
        "TEND_CONV850_12h":  tend_conv850_12h,
        "TEND_q850_6h":      tend_q850_6h,
        "RH_700":            rh700,
        "lapse_rate":        lapse_rate,
        "WSPD_850":          wspd850,
        "VORT_850":          vort850,
        "WSPD_200":          wspd200,
        "DIV_500":           div500,
    }

    X   = np.column_stack([preds[p].ravel().astype(np.float32) for p in PREDICTORS])
    X_s = (X - scaler["mean"]) / scaler["std"]
    with torch.no_grad():
        ln_pred = model(torch.tensor(X_s, dtype=torch.float32).to(DEVICE)).cpu().numpy()
    precip = np.clip(np.exp(ln_pred) - EPS, 0, None)
    precip = precip.reshape(len(lat), len(lon)).astype(np.float32)
    return lat, lon, precip


def main():
    init_time = get_cycle_time()
    PRECIP_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" Aurora MLP Precipitation Derivation")
    print(f" Init time  : {init_time}")
    print(f" Forecast   : {FORECAST_DIR}")
    print(f" Output     : {PRECIP_DIR}")
    print(f" MLP models : {MLP_MODEL_DIR}")
    print("=" * 60)

    leads     = list(range(6, 169, 6))  # 6h to 168h, 28 steps
    ok        = 0
    skipped   = 0
    failed    = 0

    for lead in leads:
        fpath     = make_nc_path(init_time, lead)
        out_path  = make_precip_path(init_time, lead)
        valid_time = init_time + timedelta(hours=lead)

        if out_path.exists():
            print(f"  [SKIP] lead +{lead}h — already exists")
            skipped += 1
            continue

        if not fpath.exists():
            print(f"  [SKIP] lead +{lead}h — forecast file not found")
            skipped += 1
            continue

        print(f"  [DERIVE] lead +{lead}h ({valid_time.strftime('%Y-%m-%d %H UTC')}) ...", end=" ", flush=True)
        try:
            model, scaler = load_model(valid_time.month)
            lat, lon, precip = derive_one(fpath, init_time, lead, model, scaler)

            ds_out = xr.Dataset(
                {"precip_mm": (["lat", "lon"], precip)},
                coords={"lat": lat, "lon": lon}
            )
            ds_out["precip_mm"].attrs = {
                "units":    "mm",
                "method":  "MLP",
                "long_name": "MLP-derived 6-hourly precipitation"
            }
            ds_out.attrs = {
                "model":      "Aurora",
                "version":    "mlp",
                "init_time":  str(init_time),
                "valid_time": str(valid_time),
                "lead_time":  lead,
            }
            ds_out.to_netcdf(out_path)
            print("OK")
            ok += 1
        except Exception as e:
            print(f"FAIL — {e}")
            failed += 1

    print("")
    print("=" * 60)
    print(f" Done! OK: {ok}  Skipped: {skipped}  Failed: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()

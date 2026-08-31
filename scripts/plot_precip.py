#!/usr/bin/env python3
"""
Aurora precipitation plot — log colorscale.
Generates PNG frames and animated GIF per cycle.
"""

import os
import sys
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime
from scipy.ndimage import gaussian_filter
import imageio
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PRECIP_DIR       = config.PRECIP_DIR
GIF_DIR          = config.PLOTS_PRECIP_GIF_DIR
FRAMES_DIR       = config.PLOTS_PRECIP_FRAMES_DIR
DOMAIN           = {"lat_min": -12, "lat_max": 23, "lon_min": 92, "lon_max": 127}

PRECIP_LEVELS = [0, 0.1, 0.25, 0.62, 1.55, 3.87, 9.66, 24.1, 60.13, 150]
PRECIP_COLORS = [
    "#ffffff", "#b5e3f9", "#6fb1df", "#489b9f", "#5cbb48",
    "#e7e25a", "#f7963b", "#e64a29", "#c51d25",
]
PRECIP_CMAP = mcolors.ListedColormap(PRECIP_COLORS)
PRECIP_CMAP.set_over("#921519")
PRECIP_NORM = mcolors.BoundaryNorm(PRECIP_LEVELS, PRECIP_CMAP.N)
SIGMA_RAIN  = 0


def get_cycle_time():
    cp = os.environ.get("CYLC_TASK_CYCLE_POINT")
    if cp:
        try:
            return datetime.strptime(cp, "%Y%m%dT%H%MZ")
        except ValueError:
            pass
    return datetime(2026, 4, 13, 6)


def subset(ds):
    if "latitude" in ds.coords:
        ds = ds.rename({"latitude": "lat", "longitude": "lon"})
    return ds.sortby("lat").sortby("lon").sel(
        lat=slice(DOMAIN["lat_min"], DOMAIN["lat_max"]),
        lon=slice(DOMAIN["lon_min"], DOMAIN["lon_max"])
    )


def base(ax, title):
    ax.set_extent([DOMAIN["lon_min"], DOMAIN["lon_max"],
                   DOMAIN["lat_min"], DOMAIN["lat_max"]], crs=ccrs.PlateCarree())
    ax.set_facecolor("white")
    ax.add_feature(cfeature.LAND,  facecolor="white", zorder=0)
    ax.add_feature(cfeature.OCEAN, facecolor="white", zorder=0)
    ax.coastlines(resolution="50m", linewidth=1.5, color="black", zorder=3)
    ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="black", zorder=3)
    gl = ax.gridlines(draw_labels=True, alpha=0.4, linestyle="--", linewidth=0.5)
    gl.top_labels   = False
    gl.right_labels = False
    ax.set_title(title, fontsize=10, fontweight="bold")


def plot_frame(init_str, step):
    fname = f"aurora_precip_{init_str}-out-{step}.nc"
    fpath = os.path.join(PRECIP_DIR, fname)
    if not os.path.exists(fpath):
        return None

    ds   = subset(xr.open_dataset(fpath))
    rain = gaussian_filter(ds["precip_mm"].squeeze().values, sigma=SIGMA_RAIN)
    lat  = ds["lat"].values
    lon  = ds["lon"].values
    ds.close()

    fig, ax = plt.subplots(1, 1, figsize=(10, 8),
                           subplot_kw={"projection": ccrs.PlateCarree()})
    base(ax, f"Aurora Precip | Init {init_str} UTC | Lead +{step}h")

    rain_plot = np.ma.masked_less(rain, 0)
    cf = ax.contourf(
        lon, lat, rain_plot,
        levels=PRECIP_LEVELS, cmap=PRECIP_CMAP, norm=PRECIP_NORM,
        extend="max", transform=ccrs.PlateCarree(), zorder=1
    )
    ax.coastlines(resolution="50m", linewidth=1.5, color="black", zorder=3)

    cax = fig.add_axes([0.83, 0.05, 0.04, 0.90])
    cb  = fig.colorbar(cf, cax=cax, ticks=PRECIP_LEVELS, spacing="uniform",
                       extend="max", extendrect=True)
    cb.set_label("6-hourly Precipitation (mm)", fontsize=9)
    cb.ax.set_yticklabels([str(l) for l in PRECIP_LEVELS], fontsize=8)
    cb.outline.set_linewidth(0.8)

    fig.suptitle("Aurora Forecast — Precipitation", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 0.83, 1])
    return fig


def main():
    init_time = get_cycle_time()
    init_str  = init_time.strftime("%Y-%m-%d_%H")
    gif_path  = os.path.join(GIF_DIR, f"aurora_precip_{init_str}.gif")

    os.makedirs(GIF_DIR, exist_ok=True)
    frames_dir = os.path.join(FRAMES_DIR, init_str)
    os.makedirs(frames_dir, exist_ok=True)

    print("=" * 60)
    print(" Aurora Precipitation Plot")
    print(f" Cycle: {init_time}")
    print("=" * 60)

    if os.path.exists(gif_path):
        print(f"GIF already exists for {init_str}, skipping.")
        return

    steps  = list(range(6, 174, 6))
    frames = []

    for step in steps:
        print(f"Plotting lead +{step}h ...", flush=True)
        fig = plot_frame(init_str, step)
        if fig is None:
            print(f"  Missing precip file for step {step}, skipping")
            continue

        png_path = os.path.join(frames_dir, f"aurora_precip_{init_str}-lead-{step:03d}h.png")
        fig.savefig(png_path, dpi=100, bbox_inches="tight")

        fig.canvas.draw()
        frame = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (4,))[:, :, :3]
        plt.close(fig)
        frames.append(frame)

    if frames:
        print(f"Saving GIF → {gif_path}")
        imageio.mimsave(gif_path, frames, fps=2, loop=0)

    print("=" * 60)
    print(" Precipitation plot complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

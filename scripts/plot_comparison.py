#!/usr/bin/env python3
"""
plot_comparison.py
Generates side-by-side Aurora vs AIFS comparison plots and animated GIF.
Reads Aurora frames from aurora_real/data/plots/frames/
Reads AIFS frames from aifs_rt/data/plots/frames/
Runs after Aurora plot finishes — by then AIFS frames should already exist.
Skips gracefully if AIFS frames not found for this cycle.
"""

import os
import sys
import numpy as np
from PIL import Image
import imageio
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ==============================================================================
# CONFIGURATION — all settings come from config.py
# ==============================================================================
AURORA_FRAMES_DIR    = config.PLOTS_FRAMES_DIR
COMPARISON_BASE_DIR  = config.COMPARISON_DIR
# ==============================================================================


def get_cycle_time():
    cycle_point = os.environ.get("CYLC_TASK_CYCLE_POINT")
    if cycle_point:
        try:
            dt = datetime.strptime(cycle_point, "%Y%m%dT%H%MZ")
            print(f"Cycle time from Cylc: {dt}")
            return dt
        except ValueError:
            print(f"WARNING: Could not parse CYLC_TASK_CYCLE_POINT='{cycle_point}'")
    INIT_TIME = datetime(2026, 4, 13, 6)
    print(f"Using manual INIT_TIME: {INIT_TIME}")
    return INIT_TIME


def main():
    init_time     = get_cycle_time()
    init_str      = init_time.strftime("%Y-%m-%d_%H")
    cycle_hour    = init_time.hour
    aifs_basename = f"aifs_{init_time.strftime('%Y-%m-%d')}_{cycle_hour:02d}z"

    print("=" * 60)
    print(" Aurora vs AIFS Comparison Plot Script")
    print(f" Cycle: {init_time}")
    print("=" * 60)

    # Paths to Aurora and AIFS frames for this cycle
    aurora_frames_dir = os.path.join(AURORA_FRAMES_DIR, init_str)
    aifs_frames_dir   = os.path.join(config.AIFS_FRAMES_DIR, aifs_basename)

    # Check if Aurora frames exist
    if not os.path.exists(aurora_frames_dir):
        print(f"Aurora frames not found: {aurora_frames_dir}")
        print("Skipping comparison.")
        return

    # Check if AIFS frames exist
    if not os.path.exists(aifs_frames_dir):
        print(f"AIFS frames not found for this cycle: {aifs_frames_dir}")
        print("Skipping comparison — AIFS may not have run this cycle yet.")
        return

    # Create output directories
    comparison_frames_dir = os.path.join(COMPARISON_BASE_DIR, "frames", init_str)
    comparison_gif_dir    = os.path.join(COMPARISON_BASE_DIR, "gif")
    os.makedirs(comparison_frames_dir, exist_ok=True)
    os.makedirs(comparison_gif_dir, exist_ok=True)

    gif_path = os.path.join(comparison_gif_dir, f"comparison_{init_str}.gif")
    if os.path.exists(gif_path):
        print(f"Comparison GIF already exists for cycle {init_str}, skipping.")
        return

    steps  = list(range(6, 174, 6))
    frames = []

    for step in steps:
        aurora_png = os.path.join(aurora_frames_dir, f"aurora_forecast_{init_str}-lead-{step:03d}h.png")
        aifs_png   = os.path.join(aifs_frames_dir,   f"{aifs_basename}-lead-{step:03d}h.png")

        if not os.path.exists(aurora_png):
            print(f"Missing Aurora frame for lead +{step}h, skipping")
            continue
        if not os.path.exists(aifs_png):
            print(f"Missing AIFS frame for lead +{step}h, skipping")
            continue

        print(f"Combining lead +{step}h ...", flush=True)

        # Open both images
        aurora_img = Image.open(aurora_png)
        aifs_img   = Image.open(aifs_png)

        # Resize AIFS to match Aurora height if needed
        if aurora_img.height != aifs_img.height:
            aifs_img = aifs_img.resize(
                (int(aifs_img.width * aurora_img.height / aifs_img.height),
                 aurora_img.height),
                Image.LANCZOS
            )

        # Stitch side by side
        combined_width  = aurora_img.width + aifs_img.width
        combined_height = aurora_img.height
        combined = Image.new("RGB", (combined_width, combined_height))
        combined.paste(aurora_img, (0, 0))
        combined.paste(aifs_img, (aurora_img.width, 0))

        # Save individual comparison PNG
        png_name = f"comparison_{init_str}-lead-{step:03d}h.png"
        png_path = os.path.join(comparison_frames_dir, png_name)
        combined.save(png_path)
        print(f"  Saved: {png_name}")

        # Add to GIF frames
        frames.append(np.array(combined))

        aurora_img.close()
        aifs_img.close()
        combined.close()

    if not frames:
        print("No comparison frames generated!")
        return

    print(f"\nSaving comparison GIF ({len(frames)} frames) → {gif_path}")
    imageio.mimsave(gif_path, frames, fps=2, loop=0)

    print("\n" + "=" * 60)
    print(f" Comparison complete!")
    print(f" GIF   : {gif_path}")
    print(f" Frames: {comparison_frames_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()

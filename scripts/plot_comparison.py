#!/usr/bin/env python3
"""
plot_comparison.py
Generates side-by-side Aurora vs AIFS comparison plots and animated GIF.
Scans all Aurora frames directories and generates comparisons for any cycle
where both Aurora and AIFS frames exist but comparison GIF doesn't yet.
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

AURORA_FRAMES_DIR   = config.PLOTS_FRAMES_DIR
COMPARISON_BASE_DIR = config.COMPARISON_DIR


def process_cycle(init_str):
    """Generate comparison for a single cycle. Returns True if successful."""
    # Parse init_str to get AIFS basename
    try:
        dt = datetime.strptime(init_str, "%Y-%m-%d_%H")
    except ValueError:
        return False

    aifs_basename     = f"aifs_{dt.strftime('%Y-%m-%d')}_{dt.hour:02d}z"
    aurora_frames_dir = os.path.join(AURORA_FRAMES_DIR, init_str)
    aifs_frames_dir   = os.path.join(config.AIFS_FRAMES_DIR, aifs_basename)

    # Check both frame directories exist
    if not os.path.exists(aurora_frames_dir):
        return False
    if not os.path.exists(aifs_frames_dir):
        print(f"  [{init_str}] AIFS frames not found — skipping")
        return False

    # Check if comparison GIF already exists
    comparison_gif_dir    = os.path.join(COMPARISON_BASE_DIR, "gif")
    comparison_frames_dir = os.path.join(COMPARISON_BASE_DIR, "frames", init_str)
    gif_path = os.path.join(comparison_gif_dir, f"comparison_{init_str}.gif")

    if os.path.exists(gif_path):
        print(f"  [{init_str}] Comparison already exists — skipping")
        return True

    print(f"  [{init_str}] Generating comparison...")
    os.makedirs(comparison_frames_dir, exist_ok=True)
    os.makedirs(comparison_gif_dir, exist_ok=True)

    steps  = list(range(6, 174, 6))
    frames = []

    for step in steps:
        aurora_png = os.path.join(aurora_frames_dir, f"aurora_forecast_{init_str}-lead-{step:03d}h.png")
        aifs_png   = os.path.join(aifs_frames_dir,   f"{aifs_basename}-lead-{step:03d}h.png")

        if not os.path.exists(aurora_png) or not os.path.exists(aifs_png):
            continue

        aurora_img = Image.open(aurora_png)
        aifs_img   = Image.open(aifs_png)

        if aurora_img.height != aifs_img.height:
            aifs_img = aifs_img.resize(
                (int(aifs_img.width * aurora_img.height / aifs_img.height),
                 aurora_img.height),
                Image.LANCZOS
            )

        combined_width  = aurora_img.width + aifs_img.width
        combined_height = aurora_img.height
        combined = Image.new("RGB", (combined_width, combined_height))
        combined.paste(aurora_img, (0, 0))
        combined.paste(aifs_img, (aurora_img.width, 0))

        png_path = os.path.join(comparison_frames_dir, f"comparison_{init_str}-lead-{step:03d}h.png")
        combined.save(png_path)
        frames.append(np.array(combined))

        aurora_img.close()
        aifs_img.close()
        combined.close()

    if not frames:
        print(f"  [{init_str}] No frames generated")
        return False

    imageio.mimsave(gif_path, frames, fps=2, loop=0)
    print(f"  [{init_str}] Done — {len(frames)} frames, GIF saved")
    return True


def main():
    print("=" * 60)
    print(" Aurora vs AIFS Comparison Plot Script")
    print(" Scanning all cycles for missing comparisons...")
    print("=" * 60)

    # Get all Aurora frame directories
    if not os.path.exists(AURORA_FRAMES_DIR):
        print(f"Aurora frames directory not found: {AURORA_FRAMES_DIR}")
        return

    cycles = sorted(os.listdir(AURORA_FRAMES_DIR))
    print(f"Found {len(cycles)} Aurora cycles to check")
    print("")

    generated = 0
    skipped   = 0

    for cycle in cycles:
        result = process_cycle(cycle)
        if result:
            generated += 1
        else:
            skipped += 1

    print("")
    print("=" * 60)
    print(f" Comparison complete!")
    print(f" Generated : {generated}")
    print(f" Skipped   : {skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()

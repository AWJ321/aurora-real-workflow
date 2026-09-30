#!/usr/bin/env python3
"""
Stitches Aurora and AIFS PNG frames side by side into double-panel plots.
Produces:
  - Archived per-cycle GIFs and frames in comparison/precip/ and comparison/wind_*/
  - Fixed-name recent/ folder (112 PNGs + 4 GIFs), overwritten every cycle
"""

import os
import sys
from datetime import datetime
from PIL import Image
import imageio
import numpy as np
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

RECENT_DIR     = config.RECENT_DIR
AIFS_PRECIP_FRAMES = config.AIFS_PRECIP_FRAMES_DIR
AIFS_WIND_FRAMES   = config.AIFS_WIND_FRAMES_DIR

PLOT_TYPES = {
    "precip": {
        "aurora_frames_dir": config.PLOTS_PRECIP_FRAMES_DIR,
        "aurora_fmt":        "aurora_precip_{init_str}-lead-{step:03d}h.png",
        "aifs_frames_dir":   AIFS_PRECIP_FRAMES,
        "aifs_subfolder":    None,   # flat under base_name/
        "aifs_fmt":          "aifs_precip_{aifs_base}-lead-{step:03d}h.png",
        "gif_dir":           config.COMPARISON_PRECIP_GIF_DIR,
        "frames_dir":        config.COMPARISON_PRECIP_FRAMES_DIR,
        "gif_prefix":        "comparison_precip",
        "recent_tag":        "",
    },
    "wind_925": {
        "aurora_frames_dir": os.path.join(config.PLOTS_WIND_FRAMES_DIR, "925hPa"),
        "aurora_fmt":        "aurora_wind925hPa_{init_str}-lead-{step:03d}h.png",
        "aifs_frames_dir":   AIFS_WIND_FRAMES,
        "aifs_subfolder":    "925hPa",
        "aifs_fmt":          "aifs_wind925hPa_{aifs_base}-lead-{step:03d}h.png",
        "gif_dir":           config.COMPARISON_WIND925_GIF_DIR,
        "frames_dir":        config.COMPARISON_WIND925_FRAMES_DIR,
        "gif_prefix":        "comparison_wind925hPa",
        "recent_tag":        "wind_925",
    },
    "wind_850": {
        "aurora_frames_dir": os.path.join(config.PLOTS_WIND_FRAMES_DIR, "850hPa"),
        "aurora_fmt":        "aurora_wind850hPa_{init_str}-lead-{step:03d}h.png",
        "aifs_frames_dir":   AIFS_WIND_FRAMES,
        "aifs_subfolder":    "850hPa",
        "aifs_fmt":          "aifs_wind850hPa_{aifs_base}-lead-{step:03d}h.png",
        "gif_dir":           config.COMPARISON_WIND850_GIF_DIR,
        "frames_dir":        config.COMPARISON_WIND850_FRAMES_DIR,
        "gif_prefix":        "comparison_wind850hPa",
        "recent_tag":        "wind_850",
    },
    "wind_700": {
        "aurora_frames_dir": os.path.join(config.PLOTS_WIND_FRAMES_DIR, "700hPa"),
        "aurora_fmt":        "aurora_wind700hPa_{init_str}-lead-{step:03d}h.png",
        "aifs_frames_dir":   AIFS_WIND_FRAMES,
        "aifs_subfolder":    "700hPa",
        "aifs_fmt":          "aifs_wind700hPa_{aifs_base}-lead-{step:03d}h.png",
        "gif_dir":           config.COMPARISON_WIND700_GIF_DIR,
        "frames_dir":        config.COMPARISON_WIND700_FRAMES_DIR,
        "gif_prefix":        "comparison_wind700hPa",
        "recent_tag":        "wind_700",
    },
}

STEPS = list(range(6, 174, 6))


def get_cycle_time():
    cp = os.environ.get("CYLC_TASK_CYCLE_POINT")
    if cp:
        try:
            return datetime.strptime(cp, "%Y%m%dT%H%MZ")
        except ValueError:
            pass
    return datetime(2026, 4, 13, 6)


def stitch(path_left, path_right):
    left  = Image.open(path_left).convert("RGB")
    right = Image.open(path_right).convert("RGB")
    if left.height != right.height:
        right = right.resize(
            (int(right.width * left.height / right.height), left.height),
            Image.LANCZOS)
    out = Image.new("RGB", (left.width + right.width, left.height), (255, 255, 255))
    out.paste(left,  (0, 0))
    out.paste(right, (left.width, 0))
    return out


def main():
    init_time = get_cycle_time()
    init_str  = init_time.strftime("%Y-%m-%d_%H")
    aifs_base = f"aifs_{init_time.strftime('%Y-%m-%d')}_{init_time.hour:02d}z"

    os.makedirs(RECENT_DIR, exist_ok=True)

    print("=" * 60)
    print(" Double-Panel Plot (Recent + Archive)")
    print(f" Aurora cycle: {init_str}")
    print(f" AIFS cycle:   {aifs_base}")
    print("=" * 60)

    for ptype, cfg in PLOT_TYPES.items():
        print(f"\n── {ptype} ──")

        gif_path   = os.path.join(cfg["gif_dir"], f"{cfg['gif_prefix']}_{init_str}.gif")
        frames_dir = os.path.join(cfg["frames_dir"], init_str)

        # Check archived GIF already exists
        archive_exists = os.path.exists(gif_path)
        if archive_exists:
            print(f"  Archive GIF exists — skipping archive, updating recent only")

        os.makedirs(frames_dir, exist_ok=True)
        gif_frames    = []
        recent_frames = []

        # AIFS frames base dir for this plot type
        if cfg["aifs_subfolder"]:
            aifs_cycle_dir = os.path.join(cfg["aifs_frames_dir"], cfg["aifs_subfolder"], aifs_base)
        else:
            aifs_cycle_dir = os.path.join(cfg["aifs_frames_dir"], aifs_base)

        aurora_cycle_dir = os.path.join(cfg["aurora_frames_dir"], init_str)

        for frame_num, step in enumerate(STEPS, start=1):
            aurora_png = os.path.join(aurora_cycle_dir,
                                      cfg["aurora_fmt"].format(init_str=init_str, step=step))
            aifs_png   = os.path.join(aifs_cycle_dir,
                                      cfg["aifs_fmt"].format(aifs_base=aifs_base, step=step))

            if not os.path.exists(aurora_png) or not os.path.exists(aifs_png):
                print(f"  [SKIP] +{step}h — missing frame(s)")
                continue

            combined = stitch(aurora_png, aifs_png)

            # Save to archive frames
            if not archive_exists:
                archive_png = os.path.join(frames_dir,
                                           f"{cfg['gif_prefix']}_{init_str}-lead-{step:03d}h.png")
                combined.save(archive_png)
                gif_frames.append(np.array(combined))

            # Always update recent
            tag = cfg['recent_tag']
            recent_png = os.path.join(RECENT_DIR, f"{frame_num:02d}{'_' + tag if tag else ''}.png")
            combined.save(recent_png)
            recent_frames.append(np.array(combined))

        # Save archive GIF
        if gif_frames:
            os.makedirs(cfg["gif_dir"], exist_ok=True)
            imageio.mimsave(gif_path, gif_frames, fps=2, loop=0)
            print(f"  Saved archive GIF: {os.path.basename(gif_path)}")

        # Save recent GIF (always overwrite)
        if recent_frames:
            recent_gif = os.path.join(RECENT_DIR, f"animation{'_' + tag if tag else ''}.gif")
            imageio.mimsave(recent_gif, recent_frames, fps=2, loop=0)
            print(f"  Saved recent GIF: animation_{cfg['recent_tag']}.gif ({len(recent_frames)} frames)")

    print("\n" + "=" * 60)
    print(" Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()

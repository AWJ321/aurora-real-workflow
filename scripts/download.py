#!/usr/bin/env python3
"""
Real-time download script for Aurora workflow.
Probe window logic:
  - Cycle 1: data already confirmed available by detect_start.py — no probing needed
  - Cycle 2: probe every 10 min for up to 7 hours
  - Cycle 3: probe every 10 min for up to 7 hours, records how long t1 data took to appear
  - Cycle 4+: adaptive wait task already slept, probe every 10 min for 2 hours
"""

import os
import sys
import time
import pathlib
from datetime import datetime, timedelta
from ecmwfapi import ECMWFService

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ==============================================================================
# CONFIGURATION — all settings come from config.py
# ==============================================================================
BASE_DIR             = config.BASE_DIR
RAW_SFC_DIR          = config.RAW_SFC_DIR
RAW_PL_DIR           = config.RAW_PL_DIR
MERGED_DIR           = config.MERGED_DIR
RETRY_INTERVAL_MINS  = config.RETRY_INTERVAL_MINS
CYCLE2_TIMEOUT_HOURS = config.CYCLE2_TIMEOUT_HOURS
STEADY_TIMEOUT_HOURS = config.STEADY_TIMEOUT_HOURS
DURATION_FILE        = config.DURATION_FILE
# ==============================================================================


def setup_dirs():
    for d in [RAW_SFC_DIR, RAW_PL_DIR, MERGED_DIR]:
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)


def get_initial_cycle_point():
    """
    Read the initial cycle point from Cylc environment variable.
    Cylc automatically sets this to whatever --initial-cycle-point
    was passed when the workflow started.
    Falls back to a manual value if running outside Cylc.
    """
    icp = os.environ.get("CYLC_WORKFLOW_INITIAL_CYCLE_POINT")
    if icp:
        return datetime.strptime(icp, "%Y%m%dT%H%MZ")
    print("WARNING: CYLC_WORKFLOW_INITIAL_CYCLE_POINT not set, using fallback")
    return datetime(2026, 4, 13, 6)


def get_cycle_time():
    """
    Read the current cycle's time from Cylc environment variable.
    Cylc automatically sets CYLC_TASK_CYCLE_POINT for every job it submits.
    """
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


def get_cycle_info(init_time):
    """
    Identify which cycle this is and return appropriate probe window.

    Cycle 1 = initial cycle point       -> attempt once (data already confirmed)
    Cycle 2 = initial cycle point + 6h  -> probe up to 7h
    Cycle 3 = initial cycle point + 12h -> probe up to 7h, record t1 duration
    Cycle 4+ = anything after           -> probe up to 2h (adaptive wait already done)

    Returns (max_wait_mins, is_cycle3)
    """
    initial_cp = get_initial_cycle_point()
    cycle2_cp  = initial_cp + timedelta(hours=6)
    cycle3_cp  = initial_cp + timedelta(hours=12)

    if init_time == initial_cp:
        print(f"  Cycle 1 — data already confirmed available, attempting once")
        return 0, False
    elif init_time == cycle2_cp:
        print(f"  Cycle 2 — probing up to {CYCLE2_TIMEOUT_HOURS}h for new data")
        return CYCLE2_TIMEOUT_HOURS * 60, False
    elif init_time == cycle3_cp:
        print(f"  Cycle 3 — probing up to {CYCLE2_TIMEOUT_HOURS}h, will record t1 data availability duration")
        return CYCLE2_TIMEOUT_HOURS * 60, True
    else:
        print(f"  Cycle 4+ — adaptive wait already done, probing up to {STEADY_TIMEOUT_HOURS}h")
        return STEADY_TIMEOUT_HOURS * 60, False


def save_duration(probe_start_time, data_found_time):
    """
    Save the measured t1 data availability duration to a file.
    This is read by wait_adaptive.sh to determine how long to sleep for cycle 4+.
    Duration is measured from when we first tried to download t1 to when it succeeded.
    """
    duration_secs           = int((data_found_time - probe_start_time).total_seconds())
    duration_hrs            = duration_secs // 3600
    duration_mins_remainder = (duration_secs % 3600) // 60
    sleep_secs              = max(0, duration_secs - 1800)
    sleep_hrs               = sleep_secs // 3600
    sleep_mins_remainder    = (sleep_secs % 3600) // 60

    with open(DURATION_FILE, "w") as f:
        f.write(f"{duration_secs}\n")

    print(f"\n  {'='*55}")
    print(f"  DATA AVAILABILITY DURATION (Cycle 3 measurement)")
    print(f"  Probing t1 started : {probe_start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  t1 data found at   : {data_found_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Duration           : {duration_hrs}h {duration_mins_remainder}m ({duration_secs}s)")
    print(f"  Cycle 4+ will sleep: {sleep_hrs}h {sleep_mins_remainder}m (duration - 30 min)")
    print(f"  Saved to           : {DURATION_FILE}")
    print(f"  {'='*55}\n")


def timestamp_str(dt):
    return dt.strftime("%Y-%m-%d_%H")


def try_download_sfc(server, dt, sfc_file):
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H%M")
    try:
        server.execute({
            "class": "od", "stream": "oper", "type": "an",
            "levtype": "sfc", "param": "167/165/166/151",
            "date": date_str, "time": time_str, "step": "0",
            "grid": "0.1/0.1", "area": "90/-180/-90/180", "expver": "1",
        }, sfc_file)
        return os.path.exists(sfc_file) and os.path.getsize(sfc_file) > 0
    except Exception as e:
        if os.path.exists(sfc_file):
            os.remove(sfc_file)
        print(f"  SFC attempt failed: {e}")
        return False


def try_download_pl(server, dt, pl_file):
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H%M")
    try:
        server.execute({
            "class": "od", "stream": "oper", "type": "an",
            "levtype": "pl",
            "levelist": "1000/925/850/700/600/500/400/300/250/200/150/100/50",
            "param": "130/131/132/133/129",
            "date": date_str, "time": time_str, "step": "0",
            "grid": "0.1/0.1", "area": "90/-180/-90/180", "expver": "1",
        }, pl_file)
        return os.path.exists(pl_file) and os.path.getsize(pl_file) > 0
    except Exception as e:
        if os.path.exists(pl_file):
            os.remove(pl_file)
        print(f"  PL attempt failed: {e}")
        return False


def download_with_retry(server, dt, max_wait_mins):
    """
    Download SFC and PL data for a given timestep with retry logic.
    Returns (sfc_file, pl_file).
    """
    ts          = timestamp_str(dt)
    sfc_file    = os.path.join(RAW_SFC_DIR, f"aurora_sfc_{ts}.grib")
    pl_file     = os.path.join(RAW_PL_DIR,  f"aurora_pl_{ts}.grib")
    max_retries = max(1, int(max_wait_mins // RETRY_INTERVAL_MINS))

    # --- SFC ---
    if os.path.exists(sfc_file) and os.path.getsize(sfc_file) > 0:
        print(f"  [SKIP] SFC already exists: {os.path.basename(sfc_file)}")
    else:
        print(f"  [DOWNLOAD] SFC {ts} ...")
        success = False
        for attempt in range(1, max_retries + 1):
            print(f"  Attempt {attempt}/{max_retries} for SFC {ts} ...")
            if try_download_sfc(server, dt, sfc_file):
                print(f"  [DONE] SFC {ts}")
                success = True
                break
            if attempt < max_retries:
                print(f"  Not available yet. Waiting {RETRY_INTERVAL_MINS} mins ...")
                time.sleep(RETRY_INTERVAL_MINS * 60)
        if not success:
            raise RuntimeError(
                f"SFC data for {ts} not available after "
                f"{max_wait_mins:.0f} minutes. Giving up."
            )

    # --- PL ---
    if os.path.exists(pl_file) and os.path.getsize(pl_file) > 0:
        print(f"  [SKIP] PL already exists: {os.path.basename(pl_file)}")
    else:
        print(f"  [DOWNLOAD] PL {ts} ...")
        success = False
        for attempt in range(1, max_retries + 1):
            print(f"  Attempt {attempt}/{max_retries} for PL {ts} ...")
            if try_download_pl(server, dt, pl_file):
                print(f"  [DONE] PL {ts}")
                success = True
                break
            if attempt < max_retries:
                print(f"  Not available yet. Waiting {RETRY_INTERVAL_MINS} mins ...")
                time.sleep(RETRY_INTERVAL_MINS * 60)
        if not success:
            raise RuntimeError(
                f"PL data for {ts} not available after "
                f"{max_wait_mins:.0f} minutes. Giving up."
            )

    return sfc_file, pl_file


def main():
    init_time                = get_cycle_time()
    t0_time                  = init_time - timedelta(hours=6)
    t1_time                  = init_time
    max_wait_mins, is_cycle3 = get_cycle_info(init_time)

    print("=" * 60)
    print(" Aurora Real-Time Download Script")
    print(f" Forecast init time : {init_time}")
    print(f" Downloading        : {t0_time} and {t1_time}")
    print(f" Max wait           : {max_wait_mins:.0f} mins")
    print(f" Record duration    : {is_cycle3}")
    print("=" * 60)

    setup_dirs()
    server = ECMWFService("mars")

    # --- Download t0 first (always old data, downloads instantly) ---
    print(f"\n--- Timestep: {timestamp_str(t0_time)} ---")
    sfc_file, pl_file = download_with_retry(server, t0_time, max_wait_mins)
    merge_timestep(sfc_file, pl_file, t0_time)

    # --- Download t1 (newest data, may need probing) ---
    print(f"\n--- Timestep: {timestamp_str(t1_time)} ---")

    # Start timer just before probing t1 — this is what we want to measure
    if is_cycle3:
        t1_probe_start = datetime.utcnow()
        print(f"  [CYCLE 3] Timer started: {t1_probe_start.strftime('%Y-%m-%d %H:%M UTC')}")

    sfc_file, pl_file = download_with_retry(server, t1_time, max_wait_mins)

    # Stop timer and save duration
    if is_cycle3:
        t1_data_found = datetime.utcnow()
        save_duration(t1_probe_start, t1_data_found)

    merge_timestep(sfc_file, pl_file, t1_time)

    print("\n" + "=" * 60)
    print(" Download complete!")
    for dt in [t0_time, t1_time]:
        ts = timestamp_str(dt)
        f  = os.path.join(MERGED_DIR, f"aurora_merged_{ts}.grib")
        if os.path.exists(f):
            print(f"  ✓ aurora_merged_{ts}.grib ({os.path.getsize(f)/(1024**2):.1f} MB)")
    print("=" * 60)


def merge_timestep(sfc_file, pl_file, dt):
    ts          = timestamp_str(dt)
    merged_file = os.path.join(MERGED_DIR, f"aurora_merged_{ts}.grib")

    if os.path.exists(merged_file) and os.path.getsize(merged_file) > 0:
        print(f"  [SKIP] Merged already exists: {os.path.basename(merged_file)}")
        return merged_file

    print(f"  [MERGE] {os.path.basename(sfc_file)} + {os.path.basename(pl_file)}")
    with open(merged_file, "wb") as out:
        for src in [sfc_file, pl_file]:
            with open(src, "rb") as f:
                out.write(f.read())

    size_mb = os.path.getsize(merged_file) / (1024 ** 2)
    print(f"  [DONE] Merged: {os.path.basename(merged_file)} ({size_mb:.1f} MB)")
    return merged_file


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Detects the latest available ECMWF data cycle point.
Prints ONLY the cycle point in Cylc format: YYYYMMDDTHHmmZ
All other output is suppressed.
"""

import os
import sys
import tempfile
import contextlib
from datetime import datetime, timedelta
from ecmwfapi import ECMWFService

MAX_LOOKBACK_DAYS = 10

def get_latest_cycle():
    server = ECMWFService("mars")

    # Get current UTC time and round down to nearest 6h cycle
    # e.g. 14:32 UTC → 12:00 UTC, since ECMWF data comes out every 6h (00, 06, 12, 18)
    now     = datetime.utcnow()
    current = now.replace(
        hour=(now.hour // 6) * 6,
        minute=0, second=0, microsecond=0
    )

    # Maximum number of 6h cycles to look back (10 days = 40 cycles)
    max_steps = MAX_LOOKBACK_DAYS * 4

    # Work backwards in time, one 6h cycle at a time
    # e.g. try 12:00, then 06:00, then 00:00, then 18:00 yesterday, etc.
    for i in range(max_steps):
        dt  = current - timedelta(hours=i * 6)
        tmp = tempfile.mktemp(suffix=".grib")

        try:
            # Try to download a tiny test file from MARS for this cycle point
            # Using a small 1x1 degree area over Singapore to minimise download size
            # All output suppressed so only the cycle point gets printed to stdout
            with open(os.devnull, 'w') as devnull:
                with contextlib.redirect_stdout(devnull):
                    with contextlib.redirect_stderr(devnull):
                        server.execute({
                            "class":   "od", "stream": "oper", "type": "an",
                            "levtype": "sfc", "param":  "167",
                            "date":    dt.strftime("%Y-%m-%d"),
                            "time":    dt.strftime("%H%M"),
                            "step":    "0",
                            "grid":    "1.0/1.0",
                            "area":    "10/100/0/110",
                            "expver":  "1",
                        }, tmp)

            # If file exists and has data, this cycle point is confirmed available on MARS
            # Print it in Cylc format (e.g. 20260406T0600Z) and stop searching
            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                os.remove(tmp)
                sys.stdout.write(dt.strftime("%Y%m%dT%H%MZ") + "\n")
                sys.stdout.flush()
                return

        except Exception:
            # MARS request failed — this cycle point not available yet, try the previous one
            pass
        finally:
            # Always clean up temp file whether request succeeded or failed
            if os.path.exists(tmp):
                os.remove(tmp)

    # If we get here, no data found in the entire lookback window — something is wrong
    sys.stderr.write("ERROR: No data found in last {} days\n".format(MAX_LOOKBACK_DAYS))
    sys.exit(1)

if __name__ == "__main__":
    get_latest_cycle()

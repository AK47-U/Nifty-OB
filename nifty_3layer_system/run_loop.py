#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lightweight runner to refresh analyzer every REFRESH_INTERVAL_SEC with heartbeat honored inside analyzer.
Use Ctrl+C to stop. Designed for manual monitoring (no auto-orders).
"""

import time
import subprocess
import sys
from pathlib import Path
from config.trading_config import CONFIG

project_root = Path(__file__).parent

python_exec = sys.executable  # use current venv python
cmd = [python_exec, str(project_root / "analyzer.py")]

print(f"[LOOP] Starting analyzer refresh loop every {CONFIG.REFRESH_INTERVAL_SEC}s. Ctrl+C to stop.")

try:
    while True:
        start = time.time()
        try:
            subprocess.run(cmd, check=False)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[LOOP] Error running analyzer: {exc}")
        elapsed = time.time() - start
        wait = max(5, CONFIG.REFRESH_INTERVAL_SEC - elapsed)
        time.sleep(wait)
except KeyboardInterrupt:
    print("[LOOP] Stopped by user.")

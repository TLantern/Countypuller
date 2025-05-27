import subprocess
import time
import sys
from pathlib import Path

# Path to the directory containing LpH.py
SCRIPT_DIR = Path(__file__).parent
LHP_PATH = SCRIPT_DIR / 'LpH.py'

while True:
    print("[run_lph_periodically] Running LpH.py for up to 10 new records...")
    result = subprocess.run([sys.executable, str(LHP_PATH), '--limit', '10'], cwd=str(SCRIPT_DIR))
    if result.returncode != 0:
        print(f"[run_lph_periodically] LpH.py exited with code {result.returncode}")
    print("[run_lph_periodically] Sleeping for 30 minutes...")
    time.sleep(30 * 60) 
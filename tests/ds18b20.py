import os
import sys
import time
from pathlib import Path

# Allow running via `python tests/ds18b20.py` from any cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from controllers import ds18b20_controller


print("DS18B20 controller test starting...")

try:
    iterations = int(os.getenv("ITERATIONS", "20"))
except Exception:
    iterations = 20

for i in range(iterations):
    try:
        c, f = ds18b20_controller.read_ds18b20_temperature()
        is_simulated = False
        print(f"[{i+1}/{iterations}] REAL: {c:.2f}°C | {f:.2f}°F")
    except Exception as e:
        c, f = ds18b20_controller._simulate_ds18b20_temperature()  # noqa: SLF001
        is_simulated = True
        print(f"[{i+1}/{iterations}] SIMULATED (reason: {e}): {c:.2f}°C | {f:.2f}°F")

    time.sleep(float(os.getenv("SLEEP_S", "1")))

print("Done.")

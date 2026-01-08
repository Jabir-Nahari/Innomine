import os
import sys
import time
from pathlib import Path

# Allow running via `python tests/scd40.py` from any cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from controllers import scd40_controller


print("SCD40 controller test starting...")

try:
    iterations = int(os.getenv("ITERATIONS", "20"))
except Exception:
    iterations = 20

scd4x = None
try:
    scd4x = scd40_controller._get_scd40()  # noqa: SLF001
    print("SCD40 detected! Reading real sensor values...")
except Exception as e:
    print(f"SCD40 not detected / init failed ({e}). Will use simulated data.")

for i in range(iterations):
    if scd4x is None:
        co2, tc, tf, rh = scd40_controller._simulate_scd40()  # noqa: SLF001
        is_simulated = True
        print(f"[{i+1}/{iterations}] SIMULATED: CO2={co2:.0f}ppm | T={tc:.2f}°C/{tf:.2f}°F | RH={rh:.1f}%")
    else:
        try:
            co2, tc, tf, rh = scd40_controller.read_scd40(scd4x)
            is_simulated = False
            print(f"[{i+1}/{iterations}] REAL: CO2={co2:.0f}ppm | T={tc:.2f}°C/{tf:.2f}°F | RH={rh:.1f}%")
        except Exception as e:
            co2, tc, tf, rh = scd40_controller._simulate_scd40()  # noqa: SLF001
            is_simulated = True
            print(f"[{i+1}/{iterations}] SIMULATED (reason: {e}): CO2={co2:.0f}ppm | T={tc:.2f}°C/{tf:.2f}°F | RH={rh:.1f}%")
            scd4x = None

    time.sleep(float(os.getenv("SLEEP_S", "2")))

print("Done.")

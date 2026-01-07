import os
import time

from controllers import scd40_controller
from db_interfaces.scd40_db import store_scd40_reading


def _db_enabled() -> bool:
    return os.getenv("ENABLE_DB", "true").lower() in {"1", "true", "yes"}


print("SCD40 controller test starting...")
print("- ENABLE_DB=", os.getenv("ENABLE_DB", "true"))

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

    if _db_enabled():
        try:
            new_id = store_scd40_reading(
                co2_ppm=co2,
                temperature_c=tc,
                temperature_f=tf,
                humidity_rh=rh,
                is_simulated=is_simulated,
            )
            print(f"  -> stored row id={new_id} (simulated={is_simulated})")
        except Exception as e:
            print(f"  -> DB store failed: {e}")

    time.sleep(float(os.getenv("SLEEP_S", "2")))

print("Done.")

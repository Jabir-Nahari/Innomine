import os
import time

from controllers import ds18b20_controller
from db_interfaces.ds18b20_db import store_ds18b20_reading


def _db_enabled() -> bool:
    return os.getenv("ENABLE_DB", "true").lower() in {"1", "true", "yes"}


print("DS18B20 controller test starting...")
print("- ENABLE_DB=", os.getenv("ENABLE_DB", "true"))

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

    if _db_enabled():
        try:
            new_id = store_ds18b20_reading(celsius=c, fahrenheit=f, is_simulated=is_simulated)
            print(f"  -> stored row id={new_id} (simulated={is_simulated})")
        except Exception as e:
            print(f"  -> DB store failed: {e}")

    time.sleep(float(os.getenv("SLEEP_S", "1")))

print("Done.")

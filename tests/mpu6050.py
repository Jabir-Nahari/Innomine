import os
import time

from controllers import mpu6050_controller
from db_interfaces.mpu6050_db import store_mpu6050_reading


def _db_enabled() -> bool:
    return os.getenv("ENABLE_DB", "true").lower() in {"1", "true", "yes"}


print("MPU6050 controller test starting...")
print("- ENABLE_DB=", os.getenv("ENABLE_DB", "true"))

try:
    iterations = int(os.getenv("ITERATIONS", "50"))
except Exception:
    iterations = 50

mpu = None
try:
    mpu = mpu6050_controller._get_mpu6050()  # noqa: SLF001
    print("MPU6050 detected! Reading real sensor values...")
except Exception as e:
    print(f"MPU6050 not detected / init failed ({e}). Will use simulated data.")

for i in range(iterations):
    if mpu is None:
        ax, ay, az, gx, gy, gz, tc, tf = mpu6050_controller._simulate_mpu6050()  # noqa: SLF001
        is_simulated = True
    else:
        try:
            ax, ay, az, gx, gy, gz, tc, tf = mpu6050_controller.read_mpu6050(mpu)
            is_simulated = False
        except Exception as e:
            ax, ay, az, gx, gy, gz, tc, tf = mpu6050_controller._simulate_mpu6050()  # noqa: SLF001
            is_simulated = True
            print(f"[{i+1}/{iterations}] MPU read failed ({e}). Switching to simulated.")
            mpu = None

    # Convert to stored units (match controller logic)
    g_const = 9.80665
    accel_x_g = ax / g_const
    accel_y_g = ay / g_const
    accel_z_g = az / g_const
    rad_to_deg = 57.29577951308232
    gyro_x_dps = gx * rad_to_deg
    gyro_y_dps = gy * rad_to_deg
    gyro_z_dps = gz * rad_to_deg

    label = "SIMULATED" if is_simulated else "REAL"
    print(
        f"[{i+1}/{iterations}] {label}: "
        f"accel_g=({accel_x_g:+.3f},{accel_y_g:+.3f},{accel_z_g:+.3f}) "
        f"gyro_dps=({gyro_x_dps:+.2f},{gyro_y_dps:+.2f},{gyro_z_dps:+.2f}) "
        f"temp={tc:.2f}°C/{tf:.2f}°F"
    )

    if _db_enabled():
        try:
            new_id = store_mpu6050_reading(
                accel_x_g=accel_x_g,
                accel_y_g=accel_y_g,
                accel_z_g=accel_z_g,
                gyro_x_dps=gyro_x_dps,
                gyro_y_dps=gyro_y_dps,
                gyro_z_dps=gyro_z_dps,
                temperature_c=tc,
                temperature_f=tf,
                is_simulated=is_simulated,
            )
            print(f"  -> stored row id={new_id} (simulated={is_simulated})")
        except Exception as e:
            print(f"  -> DB store failed: {e}")

    time.sleep(float(os.getenv("SLEEP_S", "0.2")))

print("Done.")

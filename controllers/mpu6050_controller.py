"""MPU6050 controller: reads accel/gyro/temp and stores in Postgres.

Uses "gpiozero and similar": MPU6050 is typically I2C.
This controller supports the Adafruit CircuitPython driver if installed.

Also optionally publishes readings to Kafka for the alarm worker.

Env vars (optional):
- MPU6050_POLL_INTERVAL_S (default 0.2)
- MPU6050_KAFKA_TOPIC (default mpu6050.readings)
- KAFKA_BOOTSTRAP_SERVERS (default localhost:9092)
- ENABLE_KAFKA (true/false, default false)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

try:  # optional dependencies (I2C driver stack)
    import board  # type: ignore
    import busio  # type: ignore
    import adafruit_mpu6050  # type: ignore
except Exception:  # pragma: no cover
    board = None  # type: ignore
    busio = None  # type: ignore
    adafruit_mpu6050 = None  # type: ignore

try:  # optional dependency
    from kafka import KafkaProducer  # type: ignore
except Exception:  # pragma: no cover
    KafkaProducer = None  # type: ignore

from db_interfaces.mpu6050_db import store_mpu6050_reading


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


def _get_mpu6050():
    if board is None or busio is None or adafruit_mpu6050 is None:  # pragma: no cover
        raise RuntimeError(
            "MPU6050 driver not available. Install adafruit-circuitpython-mpu6050 and dependencies."
        )

    i2c = busio.I2C(board.SCL, board.SDA)
    return adafruit_mpu6050.MPU6050(i2c)


def read_mpu6050(
    mpu=None,
) -> Tuple[float, float, float, float, float, float, float, float]:
    """Return accel (x,y,z) in m/s^2, gyro (x,y,z) rad/s, temp C/F."""
    if mpu is None:
        mpu = _get_mpu6050()

    ax, ay, az = mpu.acceleration
    gx, gy, gz = mpu.gyro
    temp_c = float(mpu.temperature)
    return (
        float(ax),
        float(ay),
        float(az),
        float(gx),
        float(gy),
        float(gz),
        temp_c,
        _c_to_f(temp_c),
    )


def _get_kafka_producer():
    if os.getenv("ENABLE_KAFKA", "false").lower() not in {"1", "true", "yes"}:
        return None

    if KafkaProducer is None:  # pragma: no cover
        raise RuntimeError(
            "Kafka not available. Install kafka-python to enable alarm streaming."
        )

    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    return KafkaProducer(
        bootstrap_servers=servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def run_poll_loop(
    *,
    poll_interval_s: Optional[float] = None,
    kafka_topic: Optional[str] = None,
) -> None:
    interval = (
        float(poll_interval_s)
        if poll_interval_s is not None
        else float(os.getenv("MPU6050_POLL_INTERVAL_S", "0.2"))
    )
    topic = kafka_topic or os.getenv("MPU6050_KAFKA_TOPIC", "mpu6050.readings")

    mpu = _get_mpu6050()
    producer = _get_kafka_producer()

    while True:
        recorded_at = _utc_now()
        ax, ay, az, gx, gy, gz, temp_c, temp_f = read_mpu6050(mpu)

        # Convert to more standard units for storage:
        # - accel from m/s^2 -> g
        # - gyro from rad/s -> deg/s
        g_const = 9.80665
        accel_x_g = ax / g_const
        accel_y_g = ay / g_const
        accel_z_g = az / g_const
        rad_to_deg = 57.29577951308232
        gyro_x_dps = gx * rad_to_deg
        gyro_y_dps = gy * rad_to_deg
        gyro_z_dps = gz * rad_to_deg

        store_mpu6050_reading(
            accel_x_g=accel_x_g,
            accel_y_g=accel_y_g,
            accel_z_g=accel_z_g,
            gyro_x_dps=gyro_x_dps,
            gyro_y_dps=gyro_y_dps,
            gyro_z_dps=gyro_z_dps,
            temperature_c=temp_c,
            temperature_f=temp_f,
            recorded_at=recorded_at,
        )

        if producer is not None:
            producer.send(
                topic,
                {
                    "sensor": "mpu6050",
                    "recorded_at": recorded_at.isoformat(),
                    "accel_x_g": accel_x_g,
                    "accel_y_g": accel_y_g,
                    "accel_z_g": accel_z_g,
                    "gyro_x_dps": gyro_x_dps,
                    "gyro_y_dps": gyro_y_dps,
                    "gyro_z_dps": gyro_z_dps,
                    "temperature_c": temp_c,
                    "temperature_f": temp_f,
                },
            )

        time.sleep(interval)


if __name__ == "__main__":
    run_poll_loop()

"""DS18B20 controller: reads temperature and stores it in Postgres.

Hardware reading approaches ("gpiozero and similar"):
- Primary: w1thermsensor (recommended for DS18B20)
- Fallback: direct read from /sys/bus/w1/devices/*/w1_slave (Linux)

Also optionally publishes readings to Kafka for the alarm worker.

Env vars (optional):
- DS18B20_POLL_INTERVAL_S (default 2)
- DS18B20_KAFKA_TOPIC (default ds18b20.readings)
- KAFKA_BOOTSTRAP_SERVERS (default localhost:9092)
- ENABLE_KAFKA (true/false, default false)
"""

from __future__ import annotations

import logging
import json
import os
import math
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

try:  # optional dependency
    from kafka import KafkaProducer  # type: ignore
except Exception:  # pragma: no cover
    KafkaProducer = None  # type: ignore

try:  # optional dependency
    from w1thermsensor import W1ThermSensor  # type: ignore
except Exception:  # pragma: no cover
    W1ThermSensor = None  # type: ignore

from db_interfaces.ds18b20_db import store_ds18b20_reading, ensure_ds18b20_table_exists


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


def _get_sensor():
    """Return W1ThermSensor instance if available."""
    if W1ThermSensor is not None:
        try:
            return W1ThermSensor()
        except Exception:
            return None
    return None

def read_ds18b20_temperature(sensor=None) -> Tuple[float, float]:
    """Return (celsius, fahrenheit)."""
    # Use passed sensor instance if available (Preferred)
    if sensor is not None:
        c = float(sensor.get_temperature())
        return c, _c_to_f(c)

    # Legacy/Fallback: Initialize on spot (not recommended for loops)
    if W1ThermSensor is not None:
        try:
            sensor = W1ThermSensor()
            c = float(sensor.get_temperature())
            return c, _c_to_f(c)
        except Exception:
            pass

    # Fallback: sysfs path (Linux only)
    base = "/sys/bus/w1/devices"
    if not os.path.isdir(base):
        raise RuntimeError(
            "DS18B20 not available: install w1thermsensor or enable Linux w1 sysfs."
        )

    candidates = [d for d in os.listdir(base) if d.startswith("28-")]
    if not candidates:
        raise RuntimeError(
            "DS18B20 not found under /sys/bus/w1/devices (no 28-* device)."
        )

    device_dir = os.path.join(base, candidates[0])
    w1_slave = os.path.join(device_dir, "w1_slave")

    with open(w1_slave, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()

    if len(lines) < 2 or not lines[0].strip().endswith("YES"):
        raise RuntimeError("DS18B20 CRC check failed while reading w1_slave")

    # Example second line: '... t=21562'
    parts = lines[1].split("t=")
    if len(parts) != 2:
        raise RuntimeError("Unexpected DS18B20 w1_slave format")

    c = float(parts[1]) / 1000.0
    return c, _c_to_f(c)


def _simulate_ds18b20_temperature() -> Tuple[float, float]:
    # Stable, obviously-fake but plausible values.
    t = time.time()
    c = 22.0 + 2.0 * math.sin(t / 30.0)
    return float(c), _c_to_f(float(c))


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
        else float(os.getenv("DS18B20_POLL_INTERVAL_S", "2"))
    )
    topic = kafka_topic or os.getenv("DS18B20_KAFKA_TOPIC", "ds18b20.readings")
    producer = _get_kafka_producer()

    logger.info("DS18B20 Controller v2.0 - SINGLE SENSOR MODE")
    # Initialize DB table once to avoid deadlocks
    try:
        ensure_ds18b20_table_exists()
    except Exception as e:
        logger.error(f"Failed to ensure DB table: {e}")

    # Initialize sensor once
    sensor = None
    is_simulated = False
    try:
        sensor = _get_sensor()
        if sensor is None and W1ThermSensor is not None:
             logger.warning("W1ThermSensor installed but failed to init. Using sysfs fallback or sim.")
    except Exception as e:
        logger.warning(f"Sensor init failed: {e}")

    while True:
        recorded_at = _utc_now()
        
        # If we failed to get sensor initially, maybe retry? 
        # For now, if sensor is None, read() falls back to sysfs
        
        try:
            c, f = read_ds18b20_temperature(sensor)
            is_simulated = False # Reset if successful
        except Exception as e:
            is_simulated = True
            c, f = _simulate_ds18b20_temperature()
            logger.warning(
                "DS18B20 read failed (%s). USING SIMULATED DATA.",
                e,
            )

        store_ds18b20_reading(
            celsius=c,
            fahrenheit=f,
            is_simulated=is_simulated,
            recorded_at=recorded_at,
        )

        if producer is not None:
            producer.send(
                topic,
                {
                    "sensor": "ds18b20",
                    "recorded_at": recorded_at.isoformat(),
                    "celsius": c,
                    "fahrenheit": f,
                    "is_simulated": is_simulated,
                },
            )

        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_poll_loop()

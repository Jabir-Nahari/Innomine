"""SCD40 controller: reads CO2/temp/humidity and stores in Postgres.

Uses "gpiozero and similar": SCD40 is typically I2C, so this uses
Adafruit CircuitPython driver if installed.

Also optionally publishes readings to Kafka for the alarm worker.

Env vars (optional):
- SCD40_POLL_INTERVAL_S (default 5)
- SCD40_KAFKA_TOPIC (default scd40.readings)
- KAFKA_BOOTSTRAP_SERVERS (default localhost:9092)
- ENABLE_KAFKA (true/false, default false)
"""

from __future__ import annotations

import logging
import json
import math
import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

try:  # optional dependency
    import adafruit_scd4x  # type: ignore
except Exception:  # pragma: no cover
    adafruit_scd4x = None  # type: ignore

try:  # optional dependency
    from kafka import KafkaProducer  # type: ignore
except Exception:  # pragma: no cover
    KafkaProducer = None  # type: ignore

from db_interfaces.scd40_db import store_scd40_reading
from controllers.i2c_utils import get_i2c, is_address_present, normalize_i2c_address


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


def _get_scd40():
    """Return an initialized SCD4x instance (adafruit driver)."""
    if adafruit_scd4x is None:  # pragma: no cover
        raise RuntimeError(
            "SCD40 driver not available. Install adafruit-circuitpython-scd4x and dependencies."
        )

    i2c = get_i2c()
    addr = normalize_i2c_address(os.getenv("SCD40_I2C_ADDRESS", "0x62"), 0x62)
    if not is_address_present(addr, i2c=i2c):
        raise RuntimeError(
            f"SCD40 not detected on I2C (expected address 0x{addr:02x})."
        )

    scd4x = adafruit_scd4x.SCD4X(i2c)
    scd4x.start_periodic_measurement()
    return scd4x


def read_scd40(scd4x=None) -> Tuple[float, float, float, float]:
    """Return (co2_ppm, temp_c, temp_f, humidity_rh)."""
    if scd4x is None:
        scd4x = _get_scd40()

    # Wait until data is ready
    while not scd4x.data_ready:
        time.sleep(0.2)

    co2 = float(scd4x.CO2)
    temp_c = float(scd4x.temperature)
    hum = float(scd4x.relative_humidity)
    return co2, temp_c, _c_to_f(temp_c), hum


def _simulate_scd40() -> Tuple[float, float, float, float]:
    t = time.time()
    # CO2 baseline with a smooth wave (clearly simulation when logged)
    co2 = 600.0 + 150.0 * math.sin(t / 20.0)
    temp_c = 23.0 + 1.0 * math.sin(t / 45.0)
    hum = 45.0 + 5.0 * math.sin(t / 30.0)
    return float(co2), float(temp_c), _c_to_f(float(temp_c)), float(hum)


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
        else float(os.getenv("SCD40_POLL_INTERVAL_S", "5"))
    )
    topic = kafka_topic or os.getenv("SCD40_KAFKA_TOPIC", "scd40.readings")

    scd4x = None
    is_simulated = False
    try:
        scd4x = _get_scd40()
    except Exception as e:
        is_simulated = True
        logger.warning("SCD40 init failed (%s). USING SIMULATED DATA.", e)
    producer = _get_kafka_producer()

    while True:
        recorded_at = _utc_now()
        if is_simulated:
            co2, temp_c, temp_f, hum = _simulate_scd40()
        else:
            try:
                co2, temp_c, temp_f, hum = read_scd40(scd4x)
            except Exception as e:
                is_simulated = True
                logger.warning("SCD40 read failed (%s). SWITCHING TO SIMULATED DATA.", e)
                co2, temp_c, temp_f, hum = _simulate_scd40()

        store_scd40_reading(
            co2_ppm=co2,
            temperature_c=temp_c,
            temperature_f=temp_f,
            humidity_rh=hum,
            is_simulated=is_simulated,
            recorded_at=recorded_at,
        )

        if producer is not None:
            producer.send(
                topic,
                {
                    "sensor": "scd40",
                    "recorded_at": recorded_at.isoformat(),
                    "co2_ppm": co2,
                    "temperature_c": temp_c,
                    "temperature_f": temp_f,
                    "humidity_rh": hum,
                    "is_simulated": is_simulated,
                },
            )

        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_poll_loop()

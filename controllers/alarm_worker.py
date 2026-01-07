"""Kafka-based alarm worker that drives a buzzer.

- Consumes sensor reading events from Kafka.
- Checks thresholds (temperature, CO2, etc.).
- If exceeded: buzzes (gpiozero) and publishes an alarm event.
- Also logs alarm events to Postgres.

Kafka dependency:
- kafka-python

GPIO dependency (on Raspberry Pi):
- gpiozero

Env vars:
- KAFKA_BOOTSTRAP_SERVERS (default localhost:9092)
- ALARM_CONSUME_TOPICS (comma-separated; default: ds18b20.readings,scd40.readings,mpu6050.readings)
- ALARM_PUBLISH_TOPIC (default alarms.events)

Thresholds:
- TEMP_C_CRITICAL (default 50)
- CO2_PPM_CRITICAL (default 2000)
- HUMIDITY_RH_CRITICAL (default 90)

Buzzer:
- BUZZER_GPIO_PIN (default 17)
- BUZZER_ACTIVE_HIGH (default true)
- BUZZER_ON_S (default 0.5)
- BUZZER_OFF_S (default 0.5)
- BUZZER_BEEPS (default 3)
"""

from __future__ import annotations

import logging
import json
import os
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:  # optional dependency (Pi only)
    from gpiozero import Buzzer  # type: ignore
except Exception:  # pragma: no cover
    Buzzer = None  # type: ignore

try:  # optional dependency
    from kafka import KafkaConsumer, KafkaProducer  # type: ignore
    from kafka.errors import NoBrokersAvailable  # type: ignore
    _KAFKA_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover
    KafkaConsumer = None  # type: ignore
    KafkaProducer = None  # type: ignore
    NoBrokersAvailable = None  # type: ignore
    _KAFKA_IMPORT_ERROR = e

from db_interfaces.alarm_db import store_alarm_event


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Thresholds:
    temp_c_critical: float
    co2_ppm_critical: float
    humidity_rh_critical: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return float(default)


def _env_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return int(default)


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


def _get_thresholds() -> Thresholds:
    return Thresholds(
        temp_c_critical=_env_float("TEMP_C_CRITICAL", "50"),
        co2_ppm_critical=_env_float("CO2_PPM_CRITICAL", "2000"),
        humidity_rh_critical=_env_float("HUMIDITY_RH_CRITICAL", "90"),
    )


def _get_buzzer():
    if Buzzer is None:  # pragma: no cover
        logger.warning(
            "gpiozero not available. BUZZER OUTPUT WILL BE SIMULATED (no GPIO)."
        )

        class _SimBuzzer:
            def on(self):
                logger.warning("BUZZER SIMULATED: ON")

            def off(self):
                logger.warning("BUZZER SIMULATED: OFF")

        return _SimBuzzer()

    pin = _env_int("BUZZER_GPIO_PIN", "17")
    active_high = _env_bool("BUZZER_ACTIVE_HIGH", "true")
    return Buzzer(pin, active_high=active_high)


def _beep(buzzer) -> None:
    on_s = _env_float("BUZZER_ON_S", "0.5")
    off_s = _env_float("BUZZER_OFF_S", "0.5")
    beeps = _env_int("BUZZER_BEEPS", "3")

    for _ in range(beeps):
        buzzer.on()
        time.sleep(on_s)
        buzzer.off()
        time.sleep(off_s)


def _get_kafka():
    if KafkaConsumer is None or KafkaProducer is None:  # pragma: no cover
        raise RuntimeError(
            "Kafka client library not available (import failed). "
            "This often means the alarm worker is running under a different Python env. "
            f"Original import error: {_KAFKA_IMPORT_ERROR!r}"
        )

    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    topics = os.getenv(
        "ALARM_CONSUME_TOPICS",
        "ds18b20.readings,scd40.readings,mpu6050.readings",
    )
    consume_topics = [t.strip() for t in topics.split(",") if t.strip()]

    group_id = os.getenv("ALARM_CONSUMER_GROUP", "innomine-alarm")

    consumer = KafkaConsumer(
        *consume_topics,
        bootstrap_servers=servers,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )

    publish_topic = os.getenv("ALARM_PUBLISH_TOPIC", "alarms.events")

    producer = KafkaProducer(
        bootstrap_servers=servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    return consumer, producer, publish_topic


def _extract_float(payload: Dict[str, Any], key: str) -> Optional[float]:
    v = payload.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def evaluate_and_alarm(
    *,
    payload: Dict[str, Any],
    thresholds: Thresholds,
    buzzer,
    kafka_producer,
    alarm_topic: str,
) -> Optional[Dict[str, Any]]:
    """Return alarm event dict if triggered."""
    sensor = str(payload.get("sensor") or "unknown")

    # Normalize timestamp
    recorded_at = payload.get("recorded_at")
    if isinstance(recorded_at, str):
        ts = recorded_at
    else:
        ts = _utc_now().isoformat()

    # CO2 alarm
    co2 = _extract_float(payload, "co2_ppm")
    if co2 is not None and co2 >= thresholds.co2_ppm_critical:
        event = {
            "triggered_at": _utc_now().isoformat(),
            "sensor": sensor,
            "metric": "co2_ppm",
            "value": co2,
            "threshold": thresholds.co2_ppm_critical,
            "severity": "critical",
            "message": f"CO2 critical: {co2} ppm (>= {thresholds.co2_ppm_critical})",
            "recorded_at": ts,
        }
        _beep(buzzer)
        kafka_producer.send(alarm_topic, event)
        store_alarm_event(
            sensor=sensor,
            metric="co2_ppm",
            value=co2,
            threshold=thresholds.co2_ppm_critical,
            severity="critical",
            message=event["message"],
        )
        return event

    # Temperature alarm (prefer temperature_c key, else celsius)
    temp_c = _extract_float(payload, "temperature_c")
    if temp_c is None:
        temp_c = _extract_float(payload, "celsius")

    if temp_c is not None and temp_c >= thresholds.temp_c_critical:
        event = {
            "triggered_at": _utc_now().isoformat(),
            "sensor": sensor,
            "metric": "temperature_c",
            "value": temp_c,
            "threshold": thresholds.temp_c_critical,
            "severity": "critical",
            "message": f"Temperature critical: {temp_c} C (>= {thresholds.temp_c_critical})",
            "recorded_at": ts,
        }
        _beep(buzzer)
        kafka_producer.send(alarm_topic, event)
        store_alarm_event(
            sensor=sensor,
            metric="temperature_c",
            value=temp_c,
            threshold=thresholds.temp_c_critical,
            severity="critical",
            message=event["message"],
        )
        return event

    # Humidity alarm
    hum = _extract_float(payload, "humidity_rh")
    if hum is not None and hum >= thresholds.humidity_rh_critical:
        event = {
            "triggered_at": _utc_now().isoformat(),
            "sensor": sensor,
            "metric": "humidity_rh",
            "value": hum,
            "threshold": thresholds.humidity_rh_critical,
            "severity": "critical",
            "message": f"Humidity critical: {hum}% (>= {thresholds.humidity_rh_critical})",
            "recorded_at": ts,
        }
        _beep(buzzer)
        kafka_producer.send(alarm_topic, event)
        store_alarm_event(
            sensor=sensor,
            metric="humidity_rh",
            value=hum,
            threshold=thresholds.humidity_rh_critical,
            severity="critical",
            message=event["message"],
        )
        return event

    return None


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    # kafka-python can be extremely chatty at INFO when brokers are down.
    logging.getLogger("kafka").setLevel(logging.WARNING)

    thresholds = _get_thresholds()
    buzzer = _get_buzzer()

    backoff_s = 1.0
    max_backoff_s = float(os.getenv("KAFKA_RETRY_MAX_S", "30"))

    while True:
        try:
            consumer, producer, alarm_topic = _get_kafka()
            logger.info("Alarm worker connected to Kafka; consuming events.")
            backoff_s = 1.0

            for msg in consumer:
                payload = msg.value
                if not isinstance(payload, dict):
                    continue

                evaluate_and_alarm(
                    payload=payload,
                    thresholds=thresholds,
                    buzzer=buzzer,
                    kafka_producer=producer,
                    alarm_topic=alarm_topic,
                )

        except Exception as e:
            # If Kafka isn't running, don't crash the whole system.
            is_no_brokers = (
                NoBrokersAvailable is not None and isinstance(e, NoBrokersAvailable)
            )
            if is_no_brokers:
                logger.warning(
                    "Kafka broker not available. Alarm worker is idle (SIMULATED) and will retry in %.1fs.",
                    backoff_s,
                )
            else:
                # Print full traceback for non-broker errors (env mismatch, auth, etc.)
                traceback.print_exc()
                logger.warning(
                    "Alarm worker Kafka error (%s). Will retry in %.1fs.",
                    e,
                    backoff_s,
                )

            time.sleep(backoff_s)
            backoff_s = min(max_backoff_s, backoff_s * 2.0)


if __name__ == "__main__":
    run()

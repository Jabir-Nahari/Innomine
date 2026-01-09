"""Kafka-based alarm worker that drives a buzzer and LED.

- Consumes sensor reading events from Kafka OR polls the database directly.
- Checks thresholds (temperature, CO2, etc.).
- If exceeded: buzzes (gpiozero), lights LED, and publishes an alarm event.
- Also logs alarm events to Postgres.

Kafka dependency:
- kafka-python

GPIO dependency (on Raspberry Pi):
- gpiozero

Env vars:
- KAFKA_BOOTSTRAP_SERVERS (default localhost:9092)
- ALARM_CONSUME_TOPICS (comma-separated; default: ds18b20.readings,scd40.readings,mpu6050.readings)
- ALARM_PUBLISH_TOPIC (default alarms.events)
- ALARM_MODE (kafka or db, default: db) - Use 'db' for direct database polling

Thresholds:
- TEMP_C_CRITICAL (default 38.0) - Human body fever threshold
- CO2_PPM_CRITICAL (default 1000) - Elevated CO2, soda can detection
- HUMIDITY_RH_CRITICAL (default 85) - High humidity discomfort

Buzzer:
- BUZZER_GPIO_PIN (default 17)
- BUZZER_ACTIVE_HIGH (default true)
- BUZZER_ON_S (default 0.5)
- BUZZER_OFF_S (default 0.5)
- BUZZER_BEEPS (default 3)

LED:
- LED_GPIO_PIN (default 27)
- LED_ACTIVE_HIGH (default true)

DB Polling:
- ALARM_POLL_INTERVAL_S (default 2) - How often to check the database
"""

from __future__ import annotations

import logging
import json
import os
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:  # optional dependency (Pi only)
    from gpiozero import Buzzer, LED  # type: ignore
except Exception:  # pragma: no cover
    Buzzer = None  # type: ignore
    LED = None  # type: ignore

try:  # optional dependency
    from kafka import KafkaConsumer, KafkaProducer  # type: ignore
    from kafka.admin import KafkaAdminClient, NewTopic  # type: ignore
    from kafka.errors import NoBrokersAvailable  # type: ignore
    from kafka.errors import TopicAlreadyExistsError  # type: ignore
    _KAFKA_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover
    KafkaConsumer = None  # type: ignore
    KafkaProducer = None  # type: ignore
    KafkaAdminClient = None  # type: ignore
    NewTopic = None  # type: ignore
    NoBrokersAvailable = None  # type: ignore
    TopicAlreadyExistsError = None  # type: ignore
    _KAFKA_IMPORT_ERROR = e

from db_interfaces.alarm_db import store_alarm_event, ensure_alarm_table_exists
from db_interfaces.scd40_db import fetch_recent_scd40
from db_interfaces.ds18b20_db import fetch_recent_ds18b20
from db_interfaces.mpu6050_db import fetch_recent_mpu6050


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
        temp_c_critical=_env_float("TEMP_C_CRITICAL", "38.0"),  # Human body fever threshold
        co2_ppm_critical=_env_float("CO2_PPM_CRITICAL", "1000"),  # Soda can CO2 detection
        humidity_rh_critical=_env_float("HUMIDITY_RH_CRITICAL", "85"),  # High humidity
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


def _get_led():
    if LED is None:  # pragma: no cover
        logger.warning(
            "gpiozero not available. LED OUTPUT WILL BE SIMULATED (no GPIO)."
        )

        class _SimLED:
            def on(self):
                logger.warning("LED SIMULATED: ON")

            def off(self):
                logger.warning("LED SIMULATED: OFF")

        return _SimLED()

    pin = _env_int("LED_GPIO_PIN", "27")
    active_high = _env_bool("LED_ACTIVE_HIGH", "true")
    return LED(pin, active_high=active_high)


def _beep(buzzer, led) -> None:
    """Activate buzzer and LED for alarm indication.
    
    Reads timing settings from shared config (controllable from UI).
    """
    from controllers.alarm_config import load_config, get_buzzer_timing
    
    config = load_config()
    on_s, off_s, beeps = get_buzzer_timing(config)
    
    logger.warning(
        "🚨 ALARM TRIGGERED - Activating buzzer and LED (%d beeps, %.1fs duration)",
        beeps,
        config.buzzer_duration_s,
    )

    for _ in range(beeps):
        buzzer.on()
        if config.led_enabled:
            led.on()
        time.sleep(on_s)
        buzzer.off()
        led.off()
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

    # Ensure topics exist to avoid noisy "Topic not found in cluster metadata" errors.
    publish_topic = os.getenv("ALARM_PUBLISH_TOPIC", "alarms.events")
    all_topics = sorted({*consume_topics, publish_topic})
    if KafkaAdminClient is not None and NewTopic is not None:
        try:
            admin = KafkaAdminClient(bootstrap_servers=servers, client_id="innomine-admin")
            try:
                futures = admin.create_topics(
                    new_topics=[NewTopic(name=t, num_partitions=1, replication_factor=1) for t in all_topics],
                    validate_only=False,
                )
                for topic_name, fut in futures.items():
                    try:
                        fut.result()
                    except Exception as e:
                        if TopicAlreadyExistsError is not None and isinstance(e, TopicAlreadyExistsError):
                            continue
                        logger.warning("Kafka topic ensure failed for %s (%s)", topic_name, e)
            finally:
                try:
                    admin.close()
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Kafka admin topic ensure failed (%s)", e)

    consumer = KafkaConsumer(
        *consume_topics,
        bootstrap_servers=servers,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )

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


# Track last alarm times to avoid spamming
_last_alarm_times: Dict[str, datetime] = {}
ALARM_COOLDOWN_S = 30  # Minimum seconds between alarms for same metric


def evaluate_and_alarm(
    *,
    payload: Dict[str, Any],
    thresholds: Thresholds,
    buzzer,
    led,
    kafka_producer=None,
    alarm_topic: str = "alarms.events",
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
        alarm_key = f"{sensor}:co2_ppm"
        last_time = _last_alarm_times.get(alarm_key)
        if last_time is None or (_utc_now() - last_time).total_seconds() > ALARM_COOLDOWN_S:
            _last_alarm_times[alarm_key] = _utc_now()
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
            _beep(buzzer, led)
            if kafka_producer is not None:
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
        alarm_key = f"{sensor}:temperature_c"
        last_time = _last_alarm_times.get(alarm_key)
        if last_time is None or (_utc_now() - last_time).total_seconds() > ALARM_COOLDOWN_S:
            _last_alarm_times[alarm_key] = _utc_now()
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
            _beep(buzzer, led)
            if kafka_producer is not None:
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
        alarm_key = f"{sensor}:humidity_rh"
        last_time = _last_alarm_times.get(alarm_key)
        if last_time is None or (_utc_now() - last_time).total_seconds() > ALARM_COOLDOWN_S:
            _last_alarm_times[alarm_key] = _utc_now()
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
            _beep(buzzer, led)
            if kafka_producer is not None:
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


def run_db_polling_mode(thresholds: Thresholds, buzzer, led) -> None:
    """Poll the database directly for threshold violations."""
    poll_interval = _env_float("ALARM_POLL_INTERVAL_S", "2")
    logger.info(
        "Alarm worker running in DB polling mode [STRICT SENSORS] (interval=%.1fs). "
        "Thresholds: temp_c=%s, co2_ppm=%s, humidity_rh=%s",
        poll_interval,
        thresholds.temp_c_critical,
        thresholds.co2_ppm_critical,
        thresholds.humidity_rh_critical,
    )

    while True:
        try:
            # Check SCD40 readings (CO2, temperature, humidity)
            since = _utc_now() - timedelta(seconds=poll_interval * 2)
            scd40_rows = fetch_recent_scd40(limit=5, since=since)
            for row in scd40_rows:
                evaluate_and_alarm(
                    payload={
                        "sensor": "scd40",
                        "recorded_at": row.get("recorded_at"),
                        "co2_ppm": row.get("co2_ppm"),
                        # "temperature_c": row.get("temperature_c"), # EXPLICITLY DISABLED: Use DS18B20 for temp
                        "humidity_rh": row.get("humidity_rh"),
                    },
                    thresholds=thresholds,
                    buzzer=buzzer,
                    led=led,
                )

            # Check DS18B20 readings (temperature only)
            ds18b20_rows = fetch_recent_ds18b20(limit=5, since=since)
            for row in ds18b20_rows:
                evaluate_and_alarm(
                    payload={
                        "sensor": "ds18b20",
                        "recorded_at": row.get("recorded_at"),
                        "temperature_c": row.get("celsius"),
                    },
                    thresholds=thresholds,
                    buzzer=buzzer,
                    led=led,
                )

            # Check MPU6050 readings (temperature only - motion doesn't have thresholds yet)
            mpu6050_rows = fetch_recent_mpu6050(limit=5, since=since)
            for row in mpu6050_rows:
                evaluate_and_alarm(
                    payload={
                        "sensor": "mpu6050",
                        "recorded_at": row.get("recorded_at"),
                        # "temperature_c": row.get("temperature_c"), # EXPLICITLY DISABLED: Use DS18B20 for temp
                    },
                    thresholds=thresholds,
                    buzzer=buzzer,
                    led=led,
                )

        except Exception as e:
            logger.error("Error polling database for alarms: %s", e)
            traceback.print_exc()

        time.sleep(poll_interval)


def run_kafka_mode(thresholds: Thresholds, buzzer, led) -> None:
    """Consume sensor readings from Kafka."""
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
                    led=led,
                    kafka_producer=producer,
                    alarm_topic=alarm_topic,
                )

        except Exception as e:
            is_no_brokers = (
                NoBrokersAvailable is not None and isinstance(e, NoBrokersAvailable)
            )
            if is_no_brokers:
                logger.warning(
                    "Kafka broker not available. Alarm worker is idle and will retry in %.1fs.",
                    backoff_s,
                )
            else:
                traceback.print_exc()
                logger.warning(
                    "Alarm worker Kafka error (%s). Will retry in %.1fs.",
                    e,
                    backoff_s,
                )

            time.sleep(backoff_s)
            backoff_s = min(max_backoff_s, backoff_s * 2.0)


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    # kafka-python can be extremely chatty at INFO when brokers are down.
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("kafka.cluster").setLevel(logging.WARNING)
    logging.getLogger("kafka.coordinator").setLevel(logging.WARNING)

    thresholds = _get_thresholds()
    buzzer = _get_buzzer()
    led = _get_led()

    # Initialize DB table once to avoid deadlocks
    try:
        ensure_alarm_table_exists()
    except Exception as e:
        logger.error(f"Failed to ensure DB table: {e}")

    # Choose mode: 'db' polls database directly, 'kafka' uses Kafka consumer
    mode = os.getenv("ALARM_MODE", "db").lower()

    if mode == "kafka":
        run_kafka_mode(thresholds, buzzer, led)
    else:
        # Default to DB polling mode - works without Kafka
        run_db_polling_mode(thresholds, buzzer, led)


if __name__ == "__main__":
    run()

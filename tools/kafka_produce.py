import json
import os
import time

try:
    from kafka import KafkaProducer  # type: ignore[import-not-found]
except Exception:
    KafkaProducer = None


servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
if KafkaProducer is None:
    raise SystemExit(
        "Missing dependency: kafka-python. Install with `pip install -r requirements.txt` and try again."
    )

producer = KafkaProducer(
    bootstrap_servers=servers,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

print("Kafka producer helper starting...")
print("- KAFKA_BOOTSTRAP_SERVERS=", servers)

# Send one message to each sensor topic, including one that should trigger an alarm.
messages = [
    (
        os.getenv("DS18B20_KAFKA_TOPIC", "ds18b20.readings"),
        {
            "sensor": "ds18b20",
            "recorded_at": time.time(),
            "celsius": 60.0,
            "fahrenheit": 140.0,
            "is_simulated": True,
        },
    ),
    (
        os.getenv("SCD40_KAFKA_TOPIC", "scd40.readings"),
        {
            "sensor": "scd40",
            "recorded_at": time.time(),
            "co2_ppm": 3000.0,
            "temperature_c": 25.0,
            "temperature_f": 77.0,
            "humidity_rh": 40.0,
            "is_simulated": True,
        },
    ),
    (
        os.getenv("MPU6050_KAFKA_TOPIC", "mpu6050.readings"),
        {
            "sensor": "mpu6050",
            "recorded_at": time.time(),
            "temperature_c": 55.0,
            "temperature_f": 131.0,
            "accel_x_g": 0.0,
            "accel_y_g": 0.0,
            "accel_z_g": 1.0,
            "gyro_x_dps": 0.0,
            "gyro_y_dps": 0.0,
            "gyro_z_dps": 0.0,
            "is_simulated": True,
        },
    ),
]

for topic, payload in messages:
    print(f"Sending to {topic}: {payload}")
    producer.send(topic, payload)

producer.flush(5)
print("Done.")

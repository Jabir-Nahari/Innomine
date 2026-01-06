"""PostgreSQL storage for MPU6050 readings (accel/gyro/temp)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from db_interfaces import db as db_common


DEFAULT_TABLE_NAME = "mpu6050_readings"


@dataclass(frozen=True)
class MPU6050Reading:
    recorded_at: datetime
    accel_x_g: float
    accel_y_g: float
    accel_z_g: float
    gyro_x_dps: float
    gyro_y_dps: float
    gyro_z_dps: float
    temperature_c: float
    temperature_f: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_mpu6050_table_exists(*, table_name: str = DEFAULT_TABLE_NAME) -> None:
    ddl_table = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id BIGSERIAL PRIMARY KEY,
        recorded_at TIMESTAMPTZ NOT NULL,
        accel_x_g DOUBLE PRECISION NOT NULL,
        accel_y_g DOUBLE PRECISION NOT NULL,
        accel_z_g DOUBLE PRECISION NOT NULL,
        gyro_x_dps DOUBLE PRECISION NOT NULL,
        gyro_y_dps DOUBLE PRECISION NOT NULL,
        gyro_z_dps DOUBLE PRECISION NOT NULL,
        temperature_c DOUBLE PRECISION NOT NULL,
        temperature_f DOUBLE PRECISION NOT NULL
    );
    """

    ddl_index = f"""
    CREATE INDEX IF NOT EXISTS {table_name}_recorded_at_idx
    ON {table_name} (recorded_at DESC);
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl_table)
            cur.execute(ddl_index)
        conn.commit()


def store_mpu6050_reading(
    *,
    accel_x_g: float,
    accel_y_g: float,
    accel_z_g: float,
    gyro_x_dps: float,
    gyro_y_dps: float,
    gyro_z_dps: float,
    temperature_c: float,
    temperature_f: float,
    recorded_at: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> int:
    if recorded_at is None:
        recorded_at = _utc_now()

    ensure_mpu6050_table_exists(table_name=table_name)

    sql = f"""
    INSERT INTO {table_name} (
        recorded_at,
        accel_x_g, accel_y_g, accel_z_g,
        gyro_x_dps, gyro_y_dps, gyro_z_dps,
        temperature_c, temperature_f
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    recorded_at,
                    float(accel_x_g),
                    float(accel_y_g),
                    float(accel_z_g),
                    float(gyro_x_dps),
                    float(gyro_y_dps),
                    float(gyro_z_dps),
                    float(temperature_c),
                    float(temperature_f),
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    return int(new_id)


def fetch_recent_mpu6050(
    *,
    limit: int = 500,
    table_name: str = DEFAULT_TABLE_NAME,
):
    ensure_mpu6050_table_exists(table_name=table_name)

    sql = f"""
    SELECT
        recorded_at,
        accel_x_g, accel_y_g, accel_z_g,
        gyro_x_dps, gyro_y_dps, gyro_z_dps,
        temperature_c, temperature_f
    FROM {table_name}
    ORDER BY recorded_at DESC
    LIMIT %s;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (int(limit),))
            rows = cur.fetchall()

    return [
        {
            "recorded_at": r[0],
            "accel_x_g": r[1],
            "accel_y_g": r[2],
            "accel_z_g": r[3],
            "gyro_x_dps": r[4],
            "gyro_y_dps": r[5],
            "gyro_z_dps": r[6],
            "temperature_c": r[7],
            "temperature_f": r[8],
        }
        for r in rows
    ]

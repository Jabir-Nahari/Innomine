"""PostgreSQL storage for SCD40 readings (CO2, temperature, humidity)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from db_interfaces import db as db_common


DEFAULT_TABLE_NAME = "scd40_readings"


@dataclass(frozen=True)
class SCD40Reading:
    recorded_at: datetime
    co2_ppm: float
    temperature_c: float
    temperature_f: float
    humidity_rh: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_scd40_table_exists(*, table_name: str = DEFAULT_TABLE_NAME) -> None:
    ddl_table = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id BIGSERIAL PRIMARY KEY,
        recorded_at TIMESTAMPTZ NOT NULL,
        co2_ppm DOUBLE PRECISION NOT NULL,
        temperature_c DOUBLE PRECISION NOT NULL,
        temperature_f DOUBLE PRECISION NOT NULL,
        humidity_rh DOUBLE PRECISION NOT NULL
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

            cur.execute(
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN NOT NULL DEFAULT FALSE;"
            )
        conn.commit()


def store_scd40_reading(
    *,
    co2_ppm: float,
    temperature_c: float,
    temperature_f: float,
    humidity_rh: float,
    is_simulated: bool = False,
    recorded_at: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> int:
    if recorded_at is None:
        recorded_at = _utc_now()

    ensure_scd40_table_exists(table_name=table_name)

    sql = f"""
    INSERT INTO {table_name} (recorded_at, co2_ppm, temperature_c, temperature_f, humidity_rh, is_simulated)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    recorded_at,
                    float(co2_ppm),
                    float(temperature_c),
                    float(temperature_f),
                    float(humidity_rh),
                    bool(is_simulated),
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    return int(new_id)


def fetch_recent_scd40(
    *,
    limit: int = 500,
    since: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
):
    """Return recent rows as list of dicts (for Streamlit/Altair)."""
    ensure_scd40_table_exists(table_name=table_name)

    if since is None:
        sql = f"""
        SELECT recorded_at, co2_ppm, temperature_c, temperature_f, humidity_rh, is_simulated
        FROM {table_name}
        ORDER BY recorded_at DESC
        LIMIT %s;
        """
        params = (int(limit),)
    else:
        sql = f"""
        SELECT recorded_at, co2_ppm, temperature_c, temperature_f, humidity_rh, is_simulated
        FROM {table_name}
        WHERE recorded_at >= %s
        ORDER BY recorded_at DESC
        LIMIT %s;
        """
        params = (since, int(limit))

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "recorded_at": r[0],
            "co2_ppm": r[1],
            "temperature_c": r[2],
            "temperature_f": r[3],
            "humidity_rh": r[4],
            "is_simulated": r[5],
        }
        for r in rows
    ]

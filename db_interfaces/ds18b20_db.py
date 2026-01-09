"""PostgreSQL storage for DS18B20 readings (temperature C/F)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from db_interfaces import db as db_common


DEFAULT_TABLE_NAME = "ds18b20_readings"


@dataclass(frozen=True)
class DS18B20Reading:
    recorded_at: datetime
    celsius: float
    fahrenheit: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_ds18b20_table_exists(*, table_name: str = DEFAULT_TABLE_NAME) -> None:
    ddl_table = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id BIGSERIAL PRIMARY KEY,
        recorded_at TIMESTAMPTZ NOT NULL,
        celsius DOUBLE PRECISION NOT NULL,
        fahrenheit DOUBLE PRECISION NOT NULL
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

            # Backward-compatible schema evolution.
            cur.execute(
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN NOT NULL DEFAULT FALSE;"
            )
        conn.commit()


def store_ds18b20_reading(
    *,
    celsius: float,
    fahrenheit: float,
    is_simulated: bool = False,
    recorded_at: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> int:
    if recorded_at is None:
        recorded_at = _utc_now()

    ensure_ds18b20_table_exists(table_name=table_name)

    sql = f"""
    INSERT INTO {table_name} (recorded_at, celsius, fahrenheit, is_simulated)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (recorded_at, float(celsius), float(fahrenheit), bool(is_simulated)),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    return int(new_id)


def fetch_recent_ds18b20(
    *,
    limit: int = 500,
    since: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
):
    


    if since is None:
        sql = f"""
        SELECT recorded_at, celsius, fahrenheit, is_simulated
        FROM {table_name}
        ORDER BY recorded_at DESC
        LIMIT %s;
        """
        params = (int(limit),)
    else:
        sql = f"""
        SELECT recorded_at, celsius, fahrenheit, is_simulated
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
            "celsius": r[1],
            "fahrenheit": r[2],
            "is_simulated": r[3],
        }
        for r in rows
    ]

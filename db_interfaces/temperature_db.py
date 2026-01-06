"""PostgreSQL temperature storage helper.

Stores temperature readings (Celsius + Fahrenheit) into a PostgreSQL table,
creating the table if it doesn't already exist.

Connection configuration:
- Prefer setting `DATABASE_URL` (e.g. postgres://user:pass@host:5432/dbname)
- Or set the standard libpq env vars: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

Dependency:
- psycopg2 (or psycopg2-binary)

Example usage (from your sensor loop):

    from db_interfaces.temperature_db import store_temperature_reading

    store_temperature_reading(celsius=temperature_c, fahrenheit=temperature_f)

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from db_interfaces import db as db_common


DEFAULT_TABLE_NAME = "temperature_readings"


@dataclass(frozen=True)
class TemperatureReading:
    celsius: float
    fahrenheit: float
    recorded_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_connection():
    """Backward-compatible import path; use db_interfaces.db.get_connection."""
    return db_common.get_connection()


def ensure_temperature_table_exists(
    *,
    table_name: str = DEFAULT_TABLE_NAME,
) -> None:
    """Create the temperature table (and a timestamp index) if missing."""
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
        conn.commit()


def store_temperature_reading(
    *,
    celsius: float,
    fahrenheit: float,
    recorded_at: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> int:
    """Insert a temperature reading. Returns the inserted row id."""
    if recorded_at is None:
        recorded_at = _utc_now()

    ensure_temperature_table_exists(table_name=table_name)

    sql = f"""
    INSERT INTO {table_name} (recorded_at, celsius, fahrenheit)
    VALUES (%s, %s, %s)
    RETURNING id;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (recorded_at, float(celsius), float(fahrenheit)))
            new_id = cur.fetchone()[0]
        conn.commit()

    return int(new_id)


def fetch_recent_temperature(
    *,
    limit: int = 500,
    table_name: str = DEFAULT_TABLE_NAME,
):
    """Return recent rows as list of dicts (for Streamlit/Altair)."""
    ensure_temperature_table_exists(table_name=table_name)

    sql = f"""
    SELECT recorded_at, celsius, fahrenheit
    FROM {table_name}
    ORDER BY recorded_at DESC
    LIMIT %s;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (int(limit),))
            rows = cur.fetchall()

    return [
        {"recorded_at": r[0], "celsius": r[1], "fahrenheit": r[2]} for r in rows
    ]

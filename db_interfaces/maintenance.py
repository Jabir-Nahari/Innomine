"""Database retention / cleanup helpers.

Keeps tables from growing unbounded by deleting rows older than a cutoff.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db_interfaces import db as db_common
from db_interfaces.alarm_db import DEFAULT_TABLE_NAME as ALARM_TABLE, ensure_alarm_table_exists
from db_interfaces.ds18b20_db import DEFAULT_TABLE_NAME as DS18B20_TABLE, ensure_ds18b20_table_exists
from db_interfaces.mpu6050_db import DEFAULT_TABLE_NAME as MPU6050_TABLE, ensure_mpu6050_table_exists
from db_interfaces.scd40_db import DEFAULT_TABLE_NAME as SCD40_TABLE, ensure_scd40_table_exists
from db_interfaces.temperature_db import DEFAULT_TABLE_NAME as TEMP_TABLE, ensure_temperature_table_exists


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def delete_older_than(*, table_name: str, ts_column: str, cutoff: datetime) -> int:
    """Delete rows older than cutoff. Returns number of rows deleted."""
    sql = f"DELETE FROM {table_name} WHERE {ts_column} < %s;"

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (cutoff,))
            deleted = cur.rowcount
        conn.commit()

    return int(deleted or 0)


def cleanup_all(*, keep_days: int = 2) -> dict[str, int]:
    """Run retention cleanup across all known tables."""
    cutoff = _utc_now() - timedelta(days=int(keep_days))

    # Ensure tables exist so cleanup doesn't error on fresh DBs.
    ensure_scd40_table_exists()
    ensure_ds18b20_table_exists()
    ensure_mpu6050_table_exists()
    ensure_alarm_table_exists()
    ensure_temperature_table_exists()

    results: dict[str, int] = {}
    results[SCD40_TABLE] = delete_older_than(table_name=SCD40_TABLE, ts_column="recorded_at", cutoff=cutoff)
    results[DS18B20_TABLE] = delete_older_than(table_name=DS18B20_TABLE, ts_column="recorded_at", cutoff=cutoff)
    results[MPU6050_TABLE] = delete_older_than(table_name=MPU6050_TABLE, ts_column="recorded_at", cutoff=cutoff)
    results[ALARM_TABLE] = delete_older_than(table_name=ALARM_TABLE, ts_column="triggered_at", cutoff=cutoff)
    results[TEMP_TABLE] = delete_older_than(table_name=TEMP_TABLE, ts_column="recorded_at", cutoff=cutoff)

    return results

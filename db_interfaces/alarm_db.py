"""PostgreSQL storage for alarm events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from db_interfaces import db as db_common


DEFAULT_TABLE_NAME = "alarm_events"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_alarm_table_exists(*, table_name: str = DEFAULT_TABLE_NAME) -> None:
    ddl_table = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id BIGSERIAL PRIMARY KEY,
        triggered_at TIMESTAMPTZ NOT NULL,
        sensor TEXT NOT NULL,
        metric TEXT NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        threshold DOUBLE PRECISION NOT NULL,
        severity TEXT NOT NULL,
        message TEXT
    );
    """

    ddl_index = f"""
    CREATE INDEX IF NOT EXISTS {table_name}_triggered_at_idx
    ON {table_name} (triggered_at DESC);
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl_table)
            cur.execute(ddl_index)
        conn.commit()


def store_alarm_event(
    *,
    sensor: str,
    metric: str,
    value: float,
    threshold: float,
    severity: str,
    message: Optional[str] = None,
    triggered_at: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
) -> int:
    if triggered_at is None:
        triggered_at = _utc_now()

    ensure_alarm_table_exists(table_name=table_name)

    sql = f"""
    INSERT INTO {table_name} (triggered_at, sensor, metric, value, threshold, severity, message)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    triggered_at,
                    str(sensor),
                    str(metric),
                    float(value),
                    float(threshold),
                    str(severity),
                    message,
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()

    return int(new_id)


def fetch_recent_alarms(
    *,
    limit: int = 200,
    since: Optional[datetime] = None,
    table_name: str = DEFAULT_TABLE_NAME,
):
    


    if since is None:
        sql = f"""
        SELECT triggered_at, sensor, metric, value, threshold, severity, message
        FROM {table_name}
        ORDER BY triggered_at DESC
        LIMIT %s;
        """
        params = (int(limit),)
    else:
        sql = f"""
        SELECT triggered_at, sensor, metric, value, threshold, severity, message
        FROM {table_name}
        WHERE triggered_at >= %s
        ORDER BY triggered_at DESC
        LIMIT %s;
        """
        params = (since, int(limit))

    with db_common.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "triggered_at": r[0],
            "sensor": r[1],
            "metric": r[2],
            "value": r[3],
            "threshold": r[4],
            "severity": r[5],
            "message": r[6],
        }
        for r in rows
    ]

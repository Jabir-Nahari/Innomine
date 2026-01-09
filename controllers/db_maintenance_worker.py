"""Periodic DB retention cleanup worker.

Deletes rows older than `DB_RETENTION_DAYS` (default 2) from sensor/alarm tables.
Run this alongside controllers to keep DB size bounded.

Env vars:
- DB_RETENTION_DAYS: int, default 2
- DB_CLEANUP_INTERVAL_S: seconds between cleanup passes, default 3600

Run:
    python -m controllers.db_maintenance_worker
"""

from __future__ import annotations

import os
import time

from db_interfaces.maintenance import cleanup_all


def main() -> int:
    keep_days = int(os.getenv("DB_RETENTION_DAYS", "2"))
    interval_s = float(os.getenv("DB_CLEANUP_INTERVAL_S", "3600"))

    print(f"DB maintenance worker starting: keep_days={keep_days} interval_s={interval_s}.")

    while True:
        try:
            results = cleanup_all(keep_days=keep_days)
            deleted_total = sum(results.values())
            if deleted_total > 0:
                print(f"DB cleanup deleted {deleted_total} rows: {results}")
        except Exception as e:
            print(f"DB cleanup failed: {e}")

        time.sleep(interval_s)


if __name__ == "__main__":
    raise SystemExit(main())

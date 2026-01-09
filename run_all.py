"""Run all Innomine services concurrently.

Starts:
- DS18B20 controller
- SCD40 controller
- MPU6050 controller
- Kafka alarm worker (buzzer)
- Streamlit UI

All components share DB configuration via env vars:
- DATABASE_URL (preferred) or PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD

Kafka env vars (if enabled/needed):
- KAFKA_BOOTSTRAP_SERVERS

Run:
    python run_all.py

Notes:
- Each component is launched as its own subprocess, so they run concurrently.
- Stop with Ctrl+C; this script will terminate all child processes.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import List, Sequence, Tuple


async def _wait_for_tcp(host: str, port: int, timeout_s: float) -> bool:
    """Wait until a TCP endpoint is reachable."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host=host, port=port)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            _ = reader
            return True
        except Exception:
            await asyncio.sleep(0.5)
    return False


async def _start_process(cmd: Sequence[str]) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(*cmd)


async def _terminate_process(proc: asyncio.subprocess.Process, timeout_s: float = 5.0) -> None:
    if proc.returncode is not None:
        return

    try:
        proc.terminate()
    except ProcessLookupError:
        return

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
        return
    except asyncio.TimeoutError:
        pass

    try:
        proc.kill()
    except ProcessLookupError:
        return

    try:
        await proc.wait()
    except Exception:
        return


async def main() -> int:
    # Allow disabling UI if you want to run headless on the Pi.
    run_ui = os.getenv("RUN_STREAMLIT", "true").lower() in {"1", "true", "yes"}
    run_alarm = os.getenv("RUN_ALARM_WORKER", "true").lower() in {"1", "true", "yes"}
    run_db_maintenance = os.getenv("RUN_DB_MAINTENANCE", "true").lower() in {"1", "true", "yes"}

    # Preflight: ensure Postgres is reachable *and* credentials work.
    pg_host = os.getenv("PGHOST", "localhost")
    pg_port = int(os.getenv("PGPORT", "5432"))
    pg_wait_s = float(os.getenv("PG_WAIT_TIMEOUT_S", "30"))

    ok = await _wait_for_tcp(pg_host, pg_port, pg_wait_s)
    if not ok:
        raise SystemExit(
            "Postgres is not reachable at "
            f"{pg_host}:{pg_port}.\n"
            "Start it with: `sudo docker compose up -d postgres`\n"
            "And verify with: `sudo docker compose ps`\n"
            "(Set PGHOST/PGPORT if Postgres is elsewhere.)"
        )

    # If psycopg2 is available, validate that we can authenticate before spawning writers.
    # This avoids controller subprocesses crashing with long psycopg2 tracebacks.
    try:
        from db_interfaces.db import get_connection  # local import to keep startup flexible

        dsn = os.getenv("DATABASE_URL")
        pg_db = os.getenv("PGDATABASE")
        pg_user = os.getenv("PGUSER")
        pg_password_set = "PGPASSWORD" in os.environ

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        except Exception as e:
            raise SystemExit(
                "Postgres connection/auth failed.\n"
                f"- DATABASE_URL set: {bool(dsn)}\n"
                f"- PGHOST={pg_host} PGPORT={pg_port} PGDATABASE={pg_db!r} PGUSER={pg_user!r} PGPASSWORD set={pg_password_set}\n"
                "If you're using the provided docker-compose defaults, use:\n"
                "  export PGHOST=localhost PGPORT=5432 PGDATABASE=innomine PGUSER=innomine PGPASSWORD=innomine\n"
                "Or set DATABASE_URL like:\n"
                "  export DATABASE_URL='postgres://innomine:innomine@localhost:5432/innomine'\n"
                f"Original error: {e}"
            )
    except ImportError:
        # psycopg2 may not be installed in some environments; TCP check above still helps.
        pass

    commands: List[Tuple[str, Sequence[str]]] = [
        ("ds18b20", [sys.executable, "-m", "controllers.ds18b20_controller"]),
        ("scd40", [sys.executable, "-m", "controllers.scd40_controller"]),
        ("mpu6050", [sys.executable, "-m", "controllers.mpu6050_controller"]),
    ]

    if run_db_maintenance:
        commands.append(("db_maintenance", [sys.executable, "-m", "controllers.db_maintenance_worker"]))

    # Alarm worker requires kafka-python. If kafka import is broken (e.g., SyntaxError from old package),
    # skip it by default so the rest of the stack can run.
    if run_alarm:
        kafka_ok = True
        try:
            import kafka  # type: ignore

            _ = kafka
        except Exception as e:
            kafka_ok = False
            print(
                "Alarm worker disabled: Kafka client import failed in this Python env.\n"
                "Fix by reinstalling kafka-python (see requirements.txt) or set RUN_ALARM_WORKER=false.\n"
                f"Import error: {e!r}"
            )

        if kafka_ok:
            commands.append(("alarm", [sys.executable, "-m", "controllers.alarm_worker"]))

    # UI Mode: 'web' (default) or 'streamlit'
    ui_mode = os.getenv("UI_MODE", "web").lower()
    
    if run_ui:
        if ui_mode == "streamlit":
             commands.append(("ui", [sys.executable, "-m", "streamlit", "run", "user_interface/app.py"]))
        else:
             # Default to new web dashboard
             # Listen on 0.0.0.0 to be accessible externally
             commands.append(("ui", [sys.executable, "-m", "uvicorn", "web_dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]))

    procs: List[asyncio.subprocess.Process] = []
    try:
        for name, cmd in commands:
            print(f"Starting {name}...")
            procs.append(await _start_process(cmd))
            # Stagger startup to prevent DB deadlocks on table creation
            await asyncio.sleep(1.0)

        # If any process exits, shut everything down.
        waiters = [asyncio.create_task(p.wait()) for p in procs]
        done, pending = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)

        # Return the first finished process code (if available)
        _ = done
        returncode = next((p.returncode for p in procs if p.returncode is not None), 0)

        for task in pending:
            task.cancel()

        return int(returncode or 0)

    except asyncio.CancelledError:
        return 130
    finally:
        # Terminate children best-effort
        await asyncio.gather(*[_terminate_process(p) for p in procs], return_exceptions=True)


def _run() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Forward SIGINT/SIGTERM into task cancellation for clean shutdown.
    main_task = loop.create_task(main())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, main_task.cancel)
        except NotImplementedError:
            # Some environments (e.g. Windows) don't support add_signal_handler.
            pass

    try:
        code = loop.run_until_complete(main_task)
    finally:
        loop.close()

    raise SystemExit(code)


if __name__ == "__main__":
    _run()

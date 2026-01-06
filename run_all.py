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
from typing import List, Sequence, Tuple


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

    commands: List[Tuple[str, Sequence[str]]] = [
        ("ds18b20", ["python", "-m", "controllers.ds18b20_controller"]),
        ("scd40", ["python", "-m", "controllers.scd40_controller"]),
        ("mpu6050", ["python", "-m", "controllers.mpu6050_controller"]),
        ("alarm", ["python", "-m", "controllers.alarm_worker"]),
    ]

    if run_ui:
        commands.append(("ui", ["streamlit", "run", "user_interface/app.py"]))

    procs: List[asyncio.subprocess.Process] = []
    try:
        for _, cmd in commands:
            procs.append(await _start_process(cmd))

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

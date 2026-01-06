"""Shared I2C utilities used by multiple controllers.

MPU6050 and SCD40 both use the same I2C pins (SCL/SDA). This module provides a
consistent way to initialize the bus and scan for devices.
"""

from __future__ import annotations

from typing import List, Optional

try:  # optional dependencies (I2C stack)
    import board  # type: ignore
    import busio  # type: ignore
except Exception:  # pragma: no cover
    board = None  # type: ignore
    busio = None  # type: ignore


def get_i2c():
    """Return an initialized busio.I2C using the default SCL/SDA pins."""
    if board is None or busio is None:  # pragma: no cover
        raise RuntimeError(
            "I2C libraries not available. Install adafruit-blinka (and run on Pi) or enable simulation."
        )
    return busio.I2C(board.SCL, board.SDA)


def scan_i2c_addresses(i2c=None) -> List[int]:
    """Scan and return detected I2C device addresses as integers."""
    if i2c is None:
        i2c = get_i2c()

    # CircuitPython I2C needs explicit lock.
    while not i2c.try_lock():
        pass
    try:
        addrs = list(i2c.scan())
    finally:
        i2c.unlock()
    return [int(a) for a in addrs]


def is_address_present(address: int, *, i2c=None) -> bool:
    addrs = scan_i2c_addresses(i2c)
    return int(address) in {int(a) for a in addrs}


def normalize_i2c_address(value: str, default: int) -> int:
    """Parse hex (0x68) or decimal string to int, with default fallback."""
    if value is None:
        return int(default)
    v = value.strip().lower()
    try:
        if v.startswith("0x"):
            return int(v, 16)
        return int(v, 10)
    except Exception:
        return int(default)

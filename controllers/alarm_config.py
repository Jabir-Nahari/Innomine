"""Shared alarm configuration between UI and alarm worker.

This module provides a simple file-based configuration that allows
the UI to control alarm settings while the alarm worker reads them.

Config file: ~/.innomine_alarm_config.json
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


CONFIG_FILE = Path.home() / ".innomine_alarm_config.json"

# Default values
DEFAULT_BUZZER_DURATION_S = 3.0  # Total buzzer duration in seconds
DEFAULT_BUZZER_BEEPS = 3  # Number of beeps
DEFAULT_PWM_DUTY_CYCLE = 1.0  # 0.0 to 1.0 (volume-like for PWM buzzers)
DEFAULT_LED_ENABLED = True


@dataclass
class AlarmConfig:
    """Alarm configuration that can be modified from UI."""
    buzzer_duration_s: float = DEFAULT_BUZZER_DURATION_S
    buzzer_beeps: int = DEFAULT_BUZZER_BEEPS
    pwm_duty_cycle: float = DEFAULT_PWM_DUTY_CYCLE
    led_enabled: bool = DEFAULT_LED_ENABLED
    alarm_poll_interval_s: float = 2.0  # Default 2.0s
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "AlarmConfig":
        return cls(
            buzzer_duration_s=float(d.get("buzzer_duration_s", DEFAULT_BUZZER_DURATION_S)),
            buzzer_beeps=int(d.get("buzzer_beeps", DEFAULT_BUZZER_BEEPS)),
            pwm_duty_cycle=float(d.get("pwm_duty_cycle", DEFAULT_PWM_DUTY_CYCLE)),
            led_enabled=bool(d.get("led_enabled", DEFAULT_LED_ENABLED)),
            alarm_poll_interval_s=float(d.get("alarm_poll_interval_s", 2.0)),
        )


def save_config(config: AlarmConfig) -> None:
    """Save alarm configuration to file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save alarm config: {e}")


def load_config() -> AlarmConfig:
    """Load alarm configuration from file, or return defaults."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return AlarmConfig.from_dict(data)
    except Exception as e:
        print(f"Warning: Could not load alarm config: {e}")
    
    return AlarmConfig()


def get_buzzer_timing(config: Optional[AlarmConfig] = None) -> tuple[float, float, int]:
    """Get buzzer on/off timing from config.
    
    Returns: (on_time_s, off_time_s, beeps)
    
    The total duration = beeps * (on_time + off_time)
    So: on_time = off_time = duration / (2 * beeps)
    """
    if config is None:
        config = load_config()
    
    beeps = max(1, config.buzzer_beeps)
    duration = max(0.5, config.buzzer_duration_s)
    
    # Each beep cycle = on_time + off_time
    # Total = beeps * (on + off) = duration
    # Assuming on = off: beeps * 2 * on = duration
    on_time = duration / (2 * beeps)
    off_time = on_time
    
    return on_time, off_time, beeps

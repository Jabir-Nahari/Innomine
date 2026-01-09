"""
InnoMine Web Dashboard Backend (FastAPI).

Serves the frontend static files and provides REST API for
real-time sensor data and mining operations.
"""

from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import random
import time
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from controllers.alarm_config import load_config, save_config, AlarmConfig
from db_interfaces.alarm_db import fetch_recent_alarms
from db_interfaces.ds18b20_db import fetch_recent_ds18b20
from db_interfaces.mpu6050_db import fetch_recent_mpu6050
from db_interfaces.scd40_db import fetch_recent_scd40

# --- Configuration & Helpers ---

THRESHOLDS = {
    "temp_c_critical": 38.0,
    "co2_ppm_critical": 1000,
    "humidity_rh_critical": 85,
    "temp_c_warning": 37.0,
    "co2_ppm_warning": 800,
    "humidity_rh_warning": 70,
}

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def get_status(value: float, metric: str) -> str:
    """Safe status check handling potentially null/missing values."""
    if value is None or not isinstance(value, (int, float)):
        return "safe"
        
    if metric == "temperature_c":
        if value >= THRESHOLDS["temp_c_critical"]:
            return "danger"
        elif value >= THRESHOLDS["temp_c_warning"]:
            return "warning"
    elif metric == "co2_ppm":
        if value >= THRESHOLDS["co2_ppm_critical"]:
            return "danger"
        elif value >= THRESHOLDS["co2_ppm_warning"]:
            return "warning"
    elif metric == "humidity_rh":
        if value >= THRESHOLDS["humidity_rh_critical"]:
            return "danger"
        elif value >= THRESHOLDS["humidity_rh_warning"]:
            return "warning"
    return "safe"

# --- Models ---

class MinerStats(BaseModel):
    id: int
    name: str
    location: str
    shift: str
    heart_rate: int
    body_temp: float
    co2_ppm: Optional[float] = None
    env_temp: Optional[float] = None
    humidity: Optional[float] = None
    motion: Any = None
    battery: int
    is_real_data: bool
    status: str

class SiteHealth(BaseModel):
    active_workers: int
    avg_co2: float
    avg_temp: float
    avg_humidity: float
    active_alerts: int
    site_safety_score: int
    last_updated: str

class Alarm(BaseModel):
    id: Optional[int] = None
    triggered_at: str
    sensor: str
    metric: str
    value: float
    threshold: float
    severity: str
    message: str
    is_simulated: bool = False

class BuzzerConfig(BaseModel):
    duration_s: float
    beeps: int
    led_enabled: bool

# --- Data Simulation & Retrieval ---

def get_real_sensor_data() -> Dict[str, Any]:
    """Fetch latest real sensor readings from DB."""
    data = {}
    try:
        since = _utc_now() - timedelta(minutes=5)
        
        # SCD40
        scd = fetch_recent_scd40(limit=1, since=since)
        if scd:
            data.update({
                "co2_ppm": scd[0]["co2_ppm"],
                "temperature_c": scd[0]["temperature_c"],
                "humidity_rh": scd[0]["humidity_rh"]
            })
            
        # DS18B20 (override temp if needed, or keep separate)
        # For simplicity, let's keep DS18B20 separate or just use SCD40 for environment
        
        # MPU6050
        mpu = fetch_recent_mpu6050(limit=1, since=since)
        if mpu:
            data.update({
                "accel_x_g": mpu[0]["accel_x_g"],
                "accel_y_g": mpu[0]["accel_y_g"]
            })
            
    except Exception as e:
        print(f"Error fetching sensor data: {e}")
    return data

def get_battery_cap() -> int:
    """Read battery capacity if available on Pi."""
    try:
        # Common path for Pi juice or UPS HATs
        path = "/sys/class/power_supply/BAT0/capacity"
        with open(path, "r") as f:
            val = int(f.read().strip())
            return max(0, min(100, val))
    except Exception:
        return 100

def simulate_miner(miner_id: int, real_data: Dict[str, Any] = None) -> MinerStats:
    t = time.time() + miner_id * 100
    is_real = (miner_id == 1)
    
    # Vital signs (Simulated for all currently)
    hr = 72 + int(15 * math.sin(t / 30)) + random.randint(-5, 5)
    bt = 36.5 + 0.5 * math.sin(t / 60) + random.uniform(-0.2, 0.2)
    
    co2 = None
    temp = None
    hum = None
    motion = None

    # Environment
    if is_real and real_data:
        co2 = real_data.get("co2_ppm")
        temp = real_data.get("temperature_c")
        hum = real_data.get("humidity_rh")
        
        # USE REAL SENSOR TEMP AS BODY TEMP (per user request)
        if temp is not None:
            bt = temp

        # Motion
        if "accel_x_g" in real_data:
             motion = abs(real_data["accel_x_g"]) + abs(real_data.get("accel_y_g", 0))
        else:
             motion = 0
             
        battery = get_battery_cap()
    else:
        # Simulation logic
        co2 = 400 + 100 * math.sin(t / 45) + random.randint(-20, 20)
        temp = 22 + 3 * math.sin(t / 50) + random.uniform(-1, 1)
        hum = 45 + 10 * math.sin(t / 40) + random.uniform(-3, 3)
        motion = 0.1 + 0.2 * abs(math.sin(t / 10))
        battery = max(15, 100 - (miner_id * 10) - random.randint(0, 5))
    
    locations = ["Section A - Shaft 1", "Section B - Tunnel 2", "Section C - Main Gallery", "Section D - Extraction"]
    
    # Calculate status
    status = "safe"
    if get_status(co2, "co2_ppm") != "safe" or get_status(temp, "temperature_c") != "safe":
        status = "warning"
        # Critical check
        if (co2 and co2 >= THRESHOLDS["co2_ppm_critical"]) or (temp and temp >= THRESHOLDS["temp_c_critical"]):
            status = "danger"

    return MinerStats(
        id=miner_id,
        name=f"Worker {miner_id:03d}",
        location=locations[(miner_id - 1) % len(locations)],
        shift="Day" if datetime.now().hour < 18 else "Night",
        heart_rate=hr,
        body_temp=round(bt, 1),
        co2_ppm=round(co2) if co2 is not None else None,
        env_temp=round(temp, 1) if temp is not None else None,
        humidity=round(hum, 1) if hum is not None else None,
        motion=round(motion, 3) if motion is not None else None,
        battery=battery,
        is_real_data=is_real,
        status=status
    )

# --- FastAPI App ---

app = FastAPI(title="InnoMine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="web_dashboard/static"), name="static")
templates = Jinja2Templates(directory="web_dashboard/templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/dashboard", response_model=Dict[str, Any])
async def get_dashboard_data():
    real_data = get_real_sensor_data()
    
    # Generate miners
    miners = []
    for i in range(1, 5):
        miners.append(simulate_miner(i, real_data if i == 1 else None))
    
    # Calculate site health
    valid_co2 = [m.co2_ppm for m in miners if m.co2_ppm is not None]
    avg_co2 = sum(valid_co2) / len(valid_co2) if valid_co2 else 0
    
    valid_temp = [m.env_temp for m in miners if m.env_temp is not None]
    avg_temp = sum(valid_temp) / len(valid_temp) if valid_temp else 0
    
    alerts_count = sum(1 for m in miners if m.status != "safe")
    
    health = SiteHealth(
        active_workers=len(miners),
        avg_co2=round(avg_co2),
        avg_temp=round(avg_temp, 1),
        avg_humidity=55.0, # Placeholder
        active_alerts=alerts_count,
        site_safety_score=max(0, 100 - (alerts_count * 10)),
        last_updated=datetime.now().strftime("%H:%M:%S")
    )
    
    return {
        "health": health,
        "miners": miners,
        "unit1_raw": real_data
    }

@app.get("/api/alarms", response_model=List[Alarm])
async def get_alarms():
    # 1. Real DB alarms
    real_alarms = []
    try:
        db_rows = fetch_recent_alarms(limit=5, since=_utc_now() - timedelta(hours=1))
        for row in db_rows:
            real_alarms.append(Alarm(
                triggered_at=row.get("triggered_at", _utc_now()).strftime("%H:%M:%S"),
                sensor=str(row.get("sensor", "unknown")),
                metric=str(row.get("metric", "")),
                value=float(row.get("value", 0)),
                threshold=float(row.get("threshold", 0)),
                severity=str(row.get("severity", "warning")),
                message=str(row.get("message", "")),
                is_simulated=False
            ))
    except Exception as e:
        print(f"DB Alarm fetch error: {e}")

    # 2. Simulated alarms for demo
    sim_alarms = [
        Alarm(
            triggered_at=(datetime.now() - timedelta(minutes=2)).strftime("%H:%M"),
            sensor="SECTION A2",
            metric="GAS",
            value=0,
            threshold=0,
            severity="critical",
            message="GAS LEAK DETECTED",
            is_simulated=True
        ),
        Alarm(
            triggered_at=(datetime.now() - timedelta(minutes=5)).strftime("%H:%M"),
            sensor="CRUSHER 5",
            metric="VIB",
            value=0,
            threshold=0,
            severity="warning",
            message="EQUIPMENT MALFUNCTION",
            is_simulated=True
        )
    ]
    
    return real_alarms + sim_alarms

@app.get("/api/history/{miner_id}")
async def get_history(miner_id: int):
    # Only Unit 1 has real history
    if miner_id != 1:
        return {"labels": [], "co2": [], "temp": []}
        
    try:
        since = _utc_now() - timedelta(hours=6)
        rows = fetch_recent_scd40(limit=200, since=since)
        # Sort by time asc
        rows.sort(key=lambda x: x["recorded_at"])
        
        return {
            "labels": [r["recorded_at"].strftime("%H:%M") for r in rows],
            "co2": [r["co2_ppm"] for r in rows],
            "temp": [r["temperature_c"] for r in rows]
        }
    except Exception:
        return {"labels": [], "co2": [], "temp": []}

@app.get("/api/config")
async def get_config():
    c = load_config()
    return {
        "duration_s": c.buzzer_duration_s,
        "beeps": c.buzzer_beeps,
        "led_enabled": c.led_enabled
    }

@app.post("/api/config")
async def set_config(config: BuzzerConfig):
    c = load_config()
    c.buzzer_duration_s = config.duration_s
    c.buzzer_beeps = config.beeps
    c.led_enabled = config.led_enabled
    save_config(c)
    return {"status": "ok"}

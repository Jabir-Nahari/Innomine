"""InnoMine - The Palantir of Mines

Streamlit UI for mining safety monitoring.
Real-time sensor data for Unit 1 + simulated data for demonstration.

Run:
    streamlit run user_interface/app.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
import random
import math

import altair as alt
import pandas as pd
import streamlit as st

from db_interfaces.alarm_db import fetch_recent_alarms
from db_interfaces.ds18b20_db import fetch_recent_ds18b20
from db_interfaces.mpu6050_db import fetch_recent_mpu6050
from db_interfaces.scd40_db import fetch_recent_scd40


# ============================================================================
# Page Configuration
# ============================================================================
st.set_page_config(
    page_title="InnoMine — The Palantir of Mines",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# Thresholds
# ============================================================================
THRESHOLDS = {
    "temp_c_critical": 38.0,
    "co2_ppm_critical": 1000,
    "humidity_rh_critical": 85,
    "temp_c_warning": 37.0,
    "co2_ppm_warning": 800,
    "humidity_rh_warning": 70,
}

# ============================================================================
# Custom CSS - Palantir-style Dark Theme
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
    
    :root {
        --bg-primary: #0a0e14;
        --bg-secondary: #111827;
        --bg-card: #1a1f2e;
        --bg-card-hover: #252b3d;
        --border-color: rgba(59, 130, 246, 0.2);
        --border-glow: rgba(59, 130, 246, 0.4);
        --text-primary: #e2e8f0;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent-blue: #3b82f6;
        --accent-cyan: #06b6d4;
        --accent-green: #10b981;
        --accent-yellow: #f59e0b;
        --accent-red: #ef4444;
        --accent-purple: #8b5cf6;
    }
    
    .stApp {
        background: linear-gradient(180deg, #0a0e14 0%, #111827 50%, #0a0e14 100%);
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Main header */
    .main-header {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.95) 0%, rgba(17, 24, 39, 0.95) 100%);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1rem 2rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 0 30px rgba(59, 130, 246, 0.1);
    }
    
    .brand-title {
        font-size: 1.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.025em;
    }
    
    .brand-subtitle {
        font-size: 0.75rem;
        color: var(--text-muted);
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    
    .live-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.875rem;
        color: var(--accent-green);
        font-weight: 600;
    }
    
    .live-dot {
        width: 8px;
        height: 8px;
        background: var(--accent-green);
        border-radius: 50%;
        animation: pulse-live 2s infinite;
    }
    
    @keyframes pulse-live {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
        50% { opacity: 0.8; box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
    }
    
    /* Panel styling */
    .panel {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.9) 0%, rgba(17, 24, 39, 0.9) 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    
    .panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-color);
    }
    
    .panel-title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .panel-badge {
        font-size: 0.65rem;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .badge-live {
        background: rgba(16, 185, 129, 0.2);
        color: var(--accent-green);
        border: 1px solid var(--accent-green);
    }
    
    .badge-simulated {
        background: rgba(139, 92, 246, 0.2);
        color: var(--accent-purple);
        border: 1px solid var(--accent-purple);
    }
    
    /* Metric grid */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 0.75rem;
    }
    
    .metric-item {
        background: rgba(17, 24, 39, 0.6);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.75rem;
        text-align: center;
    }
    
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    
    .metric-value.safe { color: var(--accent-green); }
    .metric-value.warning { color: var(--accent-yellow); }
    .metric-value.danger { color: var(--accent-red); }
    
    .metric-label {
        font-size: 0.65rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }
    
    .metric-unit {
        font-size: 0.7rem;
        color: var(--text-secondary);
    }
    
    /* Alert list */
    .alert-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        max-height: 300px;
        overflow-y: auto;
    }
    
    .alert-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem;
        background: rgba(17, 24, 39, 0.6);
        border-radius: 8px;
        border-left: 3px solid var(--accent-yellow);
    }
    
    .alert-item.critical {
        border-left-color: var(--accent-red);
        background: rgba(239, 68, 68, 0.1);
    }
    
    .alert-item.warning {
        border-left-color: var(--accent-yellow);
        background: rgba(245, 158, 11, 0.1);
    }
    
    .alert-item.info {
        border-left-color: var(--accent-blue);
        background: rgba(59, 130, 246, 0.1);
    }
    
    .alert-icon {
        font-size: 1.25rem;
    }
    
    .alert-content {
        flex: 1;
    }
    
    .alert-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    
    .alert-detail {
        font-size: 0.7rem;
        color: var(--text-secondary);
    }
    
    .alert-time {
        font-size: 0.65rem;
        color: var(--text-muted);
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Miner card */
    .miner-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.95) 0%, rgba(17, 24, 39, 0.95) 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem;
        position: relative;
        overflow: hidden;
    }
    
    .miner-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-green), var(--accent-cyan));
    }
    
    .miner-card.warning::before {
        background: linear-gradient(90deg, var(--accent-yellow), var(--accent-red));
    }
    
    .miner-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }
    
    .miner-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: white;
        font-size: 0.875rem;
    }
    
    .miner-info h4 {
        margin: 0;
        font-size: 0.9rem;
        color: var(--text-primary);
    }
    
    .miner-info span {
        font-size: 0.7rem;
        color: var(--text-secondary);
    }
    
    .miner-status {
        margin-left: auto;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .miner-status.safe {
        background: rgba(16, 185, 129, 0.2);
        color: var(--accent-green);
    }
    
    .miner-status.warning {
        background: rgba(245, 158, 11, 0.2);
        color: var(--accent-yellow);
    }
    
    .miner-status.danger {
        background: rgba(239, 68, 68, 0.2);
        color: var(--accent-red);
    }
    
    /* Map placeholder */
    .map-container {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1rem;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        position: relative;
        overflow: hidden;
    }
    
    .map-grid {
        position: absolute;
        inset: 0;
        background-image: 
            linear-gradient(rgba(59, 130, 246, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59, 130, 246, 0.1) 1px, transparent 1px);
        background-size: 30px 30px;
    }
    
    .map-dot {
        width: 12px;
        height: 12px;
        background: var(--accent-green);
        border-radius: 50%;
        position: absolute;
        box-shadow: 0 0 10px var(--accent-green);
        animation: pulse-dot 2s infinite;
    }
    
    .map-dot.warning {
        background: var(--accent-yellow);
        box-shadow: 0 0 10px var(--accent-yellow);
    }
    
    @keyframes pulse-dot {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.3); }
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #111827;
    }
    
    /* Override text colors */
    .stMarkdown, p, span, label { color: var(--text-primary); }
    h1, h2, h3, h4 { color: var(--text-primary) !important; }
    
    /* Charts */
    .stAltairChart {
        background: transparent !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Helper Functions
# ============================================================================
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_status(value: float, metric: str) -> str:
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


def simulate_miner_data(miner_id: int, real_sensor_data: dict = None) -> dict:
    """Generate simulated miner data, optionally using real sensor values."""
    t = time.time() + miner_id * 100  # Offset for variety
    
    # Simulated vital signs
    heart_rate = 72 + int(15 * math.sin(t / 30)) + random.randint(-5, 5)
    body_temp = 36.5 + 0.5 * math.sin(t / 60) + random.uniform(-0.2, 0.2)
    
    # Use real environmental data if available for miner 1
    if real_sensor_data and miner_id == 1:
        co2 = real_sensor_data.get("co2_ppm", 450)
        env_temp = real_sensor_data.get("temperature_c", 24)
        humidity = real_sensor_data.get("humidity_rh", 45)
        is_real = True
    else:
        co2 = 400 + 100 * math.sin(t / 45) + random.randint(-20, 20)
        env_temp = 22 + 3 * math.sin(t / 50) + random.uniform(-1, 1)
        humidity = 45 + 10 * math.sin(t / 40) + random.uniform(-3, 3)
        is_real = False
    
    # Simulated motion/acceleration
    if real_sensor_data and miner_id == 1 and "accel_x_g" in real_sensor_data:
        motion = abs(real_sensor_data.get("accel_x_g", 0)) + abs(real_sensor_data.get("accel_y_g", 0))
    else:
        motion = 0.1 + 0.2 * abs(math.sin(t / 10)) + random.uniform(0, 0.1)
    
    # Simulated location
    locations = ["Section A - Shaft 1", "Section B - Tunnel 2", "Section C - Main Gallery", "Section D - Extraction"]
    
    return {
        "id": miner_id,
        "name": f"Worker {miner_id:03d}",
        "location": locations[(miner_id - 1) % len(locations)],
        "shift": "Day" if datetime.now().hour < 18 else "Night",
        "heart_rate": heart_rate,
        "body_temp": body_temp,
        "co2_ppm": co2,
        "env_temp": env_temp,
        "humidity": humidity,
        "motion": motion,
        "battery": max(15, 100 - (miner_id * 10) - random.randint(0, 20)),
        "is_real_data": is_real,
        "last_update": datetime.now(),
    }


def generate_simulated_alerts() -> list:
    """Generate simulated alerts for demonstration."""
    alerts = [
        {
            "type": "critical",
            "icon": "🔴",
            "title": "GAS LEAK - SECTION A2",
            "detail": "CO2 levels exceeding threshold in tunnel A2",
            "time": "2 min ago",
            "simulated": True,
        },
        {
            "type": "warning",
            "icon": "🟡",
            "title": "EQUIPMENT MALFUNCTION - CRUSHER 5",
            "detail": "Abnormal vibration detected",
            "time": "5 min ago",
            "simulated": True,
        },
        {
            "type": "warning",
            "icon": "🟡",
            "title": "PERSONNEL PROXIMITY WARNING",
            "detail": "Worker 003 near restricted zone",
            "time": "8 min ago",
            "simulated": True,
        },
        {
            "type": "info",
            "icon": "🔵",
            "title": "SHIFT CHANGE REMINDER",
            "detail": "Night shift begins in 30 minutes",
            "time": "12 min ago",
            "simulated": True,
        },
    ]
    return alerts


# ============================================================================
# Fetch Real Sensor Data
# ============================================================================
def get_real_sensor_data() -> dict:
    """Fetch the latest real sensor data from database."""
    data = {}
    
    try:
        since = _utc_now() - timedelta(minutes=5)
        
        # SCD40 - CO2, temp, humidity
        scd40_rows = fetch_recent_scd40(limit=1, since=since)
        if scd40_rows:
            latest = scd40_rows[0]
            data["co2_ppm"] = latest.get("co2_ppm")
            data["temperature_c"] = latest.get("temperature_c")
            data["humidity_rh"] = latest.get("humidity_rh")
            data["scd40_timestamp"] = latest.get("recorded_at")
        
        # DS18B20 - Temperature
        ds18b20_rows = fetch_recent_ds18b20(limit=1, since=since)
        if ds18b20_rows:
            latest = ds18b20_rows[0]
            data["ds18b20_temp"] = latest.get("celsius")
            data["ds18b20_timestamp"] = latest.get("recorded_at")
        
        # MPU6050 - Motion
        mpu6050_rows = fetch_recent_mpu6050(limit=1, since=since)
        if mpu6050_rows:
            latest = mpu6050_rows[0]
            data["accel_x_g"] = latest.get("accel_x_g")
            data["accel_y_g"] = latest.get("accel_y_g")
            data["accel_z_g"] = latest.get("accel_z_g")
            data["mpu6050_timestamp"] = latest.get("recorded_at")
    
    except Exception as e:
        st.warning(f"Could not fetch sensor data: {e}")
    
    return data


# ============================================================================
# UI Components
# ============================================================================
def render_header():
    st.markdown(f"""
    <div class="main-header">
        <div>
            <div class="brand-title">⛏️ InnoMine</div>
            <div class="brand-subtitle">The Palantir of Mines</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.5rem; font-weight: 700; color: #e2e8f0; font-family: 'JetBrains Mono', monospace;">
                {datetime.now().strftime('%H:%M:%S')}
            </div>
            <div style="font-size: 0.7rem; color: #64748b;">{datetime.now().strftime('%Y-%m-%d')}</div>
        </div>
        <div class="live-indicator">
            <div class="live-dot"></div>
            LIVE
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_site_health_panel(real_data: dict, miners: list):
    """Render the Real-Time Site Health panel."""
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <div class="panel-title">📊 Real-Time Site Health</div>
            <span class="panel-badge badge-live">LIVE</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Calculate aggregates
    avg_co2 = sum(m["co2_ppm"] for m in miners) / len(miners)
    avg_temp = sum(m["env_temp"] for m in miners) / len(miners)
    avg_humidity = sum(m["humidity"] for m in miners) / len(miners)
    active_miners = len(miners)
    alerts_count = sum(1 for m in miners if get_status(m["co2_ppm"], "co2_ppm") != "safe")
    
    st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-item">
                <div class="metric-value">{active_miners}</div>
                <div class="metric-label">Active Workers</div>
            </div>
            <div class="metric-item">
                <div class="metric-value {get_status(avg_co2, 'co2_ppm')}">{avg_co2:.0f}</div>
                <div class="metric-label">Avg CO₂ <span class="metric-unit">ppm</span></div>
            </div>
            <div class="metric-item">
                <div class="metric-value {get_status(avg_temp, 'temperature_c')}">{avg_temp:.1f}°</div>
                <div class="metric-label">Avg Temp <span class="metric-unit">°C</span></div>
            </div>
            <div class="metric-item">
                <div class="metric-value">{avg_humidity:.0f}%</div>
                <div class="metric-label">Humidity</div>
            </div>
            <div class="metric-item">
                <div class="metric-value {'danger' if alerts_count > 0 else 'safe'}">{alerts_count}</div>
                <div class="metric-label">Active Alerts</div>
            </div>
            <div class="metric-item">
                <div class="metric-value safe">98%</div>
                <div class="metric-label">Site Safety</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Real sensor data card for Unit 1
    if real_data:
        st.markdown("""
        <div class="panel" style="border-color: rgba(16, 185, 129, 0.4);">
            <div class="panel-header">
                <div class="panel-title">🎯 Unit 1 - Live Sensor Data</div>
                <span class="panel-badge badge-live">REAL DATA</span>
            </div>
        """, unsafe_allow_html=True)
        
        cols = st.columns(4)
        
        with cols[0]:
            co2 = real_data.get("co2_ppm", "N/A")
            co2_status = get_status(co2, "co2_ppm") if isinstance(co2, (int, float)) else "safe"
            co2_val = f"{co2:.0f}" if isinstance(co2, (int, float)) else str(co2)
            st.markdown(f"""
            <div class="metric-item">
                <div class="metric-value {co2_status}">{co2_val}</div>
                <div class="metric-label">CO₂ <span class="metric-unit">ppm</span></div>
            </div>
            """, unsafe_allow_html=True)
        
        with cols[1]:
            temp = real_data.get("temperature_c", "N/A")
            temp_status = get_status(temp, "temperature_c") if isinstance(temp, (int, float)) else "safe"
            temp_val = f"{temp:.1f}" if isinstance(temp, (int, float)) else str(temp)
            st.markdown(f"""
            <div class="metric-item">
                <div class="metric-value {temp_status}">{temp_val}°</div>
                <div class="metric-label">Temperature <span class="metric-unit">°C</span></div>
            </div>
            """, unsafe_allow_html=True)
        
        with cols[2]:
            hum = real_data.get("humidity_rh", "N/A")
            hum_val = f"{hum:.1f}" if isinstance(hum, (int, float)) else str(hum)
            st.markdown(f"""
            <div class="metric-item">
                <div class="metric-value">{hum_val}%</div>
                <div class="metric-label">Humidity</div>
            </div>
            """, unsafe_allow_html=True)
        
        with cols[3]:
            accel = real_data.get("accel_x_g", "N/A")
            accel_val = f"{accel:.3f}" if isinstance(accel, (int, float)) else str(accel)
            st.markdown(f"""
            <div class="metric-item">
                <div class="metric-value">{accel_val}</div>
                <div class="metric-label">Motion <span class="metric-unit">g</span></div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)


def render_alerts_panel(alerts: list, db_alarms: list):
    """Render the AI-Prioritized Alerts panel."""
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <div class="panel-title">🚨 AI-Prioritized Alerts</div>
            <span class="panel-badge badge-simulated">DEMO</span>
        </div>
        <div class="alert-list">
    """, unsafe_allow_html=True)
    
    # Add real DB alarms at the top
    for alarm in db_alarms[:3]:
        st.markdown(f"""
        <div class="alert-item critical">
            <div class="alert-icon">🔴</div>
            <div class="alert-content">
                <div class="alert-title">{alarm.get('metric', 'ALERT').upper()} - {alarm.get('sensor', 'SENSOR').upper()}</div>
                <div class="alert-detail">{alarm.get('message', 'Threshold exceeded')}</div>
            </div>
            <div class="alert-time">{alarm.get('triggered_at', datetime.now()).strftime('%H:%M') if hasattr(alarm.get('triggered_at'), 'strftime') else 'Now'}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Simulated alerts
    for alert in alerts:
        st.markdown(f"""
        <div class="alert-item {alert['type']}">
            <div class="alert-icon">{alert['icon']}</div>
            <div class="alert-content">
                <div class="alert-title">{alert['title']} <span style="color: #8b5cf6; font-size: 0.6rem;">[SIM]</span></div>
                <div class="alert-detail">{alert['detail']}</div>
            </div>
            <div class="alert-time">{alert['time']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_mine_map_panel(miners: list):
    """Render the Geospatial Mine Twin Map panel."""
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <div class="panel-title">🗺️ Geospatial Mine Twin Map</div>
            <span class="panel-badge badge-simulated">SIMULATED</span>
        </div>
        <div class="map-container">
            <div class="map-grid"></div>
    """, unsafe_allow_html=True)
    
    # Add dots for miners at pseudo-random positions
    for i, miner in enumerate(miners):
        x = 20 + (i % 4) * 60 + random.randint(-10, 10)
        y = 30 + (i // 4) * 50 + random.randint(-10, 10)
        status = "warning" if get_status(miner["co2_ppm"], "co2_ppm") != "safe" else ""
        st.markdown(f"""
            <div class="map-dot {status}" style="left: {x}%; top: {y}%;" title="{miner['name']}"></div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
            <div style="color: #64748b; font-size: 0.8rem; z-index: 10;">
                🟢 Workers are displayed as dots • Locations are simulated
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_workers_panel(miners: list):
    """Render the workers overview panel."""
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <div class="panel-title">👷 Active Workers</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    cols = st.columns(2)
    for i, miner in enumerate(miners[:4]):
        with cols[i % 2]:
            status = get_status(miner["co2_ppm"], "co2_ppm")
            badge_text = "LIVE" if miner["is_real_data"] else "SIM"
            badge_class = "badge-live" if miner["is_real_data"] else "badge-simulated"
            
            st.markdown(f"""
            <div class="miner-card {'warning' if status != 'safe' else ''}">
                <div class="miner-header">
                    <div class="miner-avatar">{miner['name'][0]}{miner['id']}</div>
                    <div class="miner-info">
                        <h4>{miner['name']} <span class="panel-badge {badge_class}">{badge_text}</span></h4>
                        <span>{miner['location']}</span>
                    </div>
                    <div class="miner-status {status}">{status.upper()}</div>
                </div>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-value">{miner['heart_rate']}</div>
                        <div class="metric-label">BPM</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">{miner['body_temp']:.1f}°</div>
                        <div class="metric-label">Body Temp</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value {status}">{miner['co2_ppm']:.0f}</div>
                        <div class="metric-label">CO₂</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">{miner['battery']}%</div>
                        <div class="metric-label">Battery</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ============================================================================
# Main App
# ============================================================================

# Fetch real sensor data
real_sensor_data = get_real_sensor_data()

# Generate miner data (1 real + 3 simulated)
miners = [simulate_miner_data(i, real_sensor_data if i == 1 else None) for i in range(1, 5)]

# Fetch real alarms from DB
try:
    db_alarms = fetch_recent_alarms(limit=5, since=_utc_now() - timedelta(hours=1))
except:
    db_alarms = []

# Generate simulated alerts
simulated_alerts = generate_simulated_alerts()

# Render UI
render_header()

# Three-column layout matching the reference
col1, col2 = st.columns([2, 1])

with col1:
    render_site_health_panel(real_sensor_data, miners)
    render_workers_panel(miners)

with col2:
    render_alerts_panel(simulated_alerts, db_alarms)
    render_mine_map_panel(miners)

# Sidebar controls
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
    refresh_s = st.slider("Refresh interval", 1, 10, 2)
    
    st.divider()
    
    st.markdown("### 📊 Data Status")
    if real_sensor_data:
        st.success("✅ Live sensor data connected")
    else:
        st.warning("⚠️ No live sensor data")
    
    st.info("ℹ️ Workers 2-4 use simulated data")
    
    st.divider()
    
    st.markdown("### 🔔 Buzzer Controls")
    import sys
    sys.path.insert(0, "/Users/jabirnahari/Desktop/Programming_Projects/Innomine")
    try:
        from controllers.alarm_config import AlarmConfig, load_config, save_config
        config = load_config()
        
        duration = st.slider("Duration (s)", 1.0, 10.0, config.buzzer_duration_s, 0.5)
        beeps = st.slider("Beeps", 1, 10, config.buzzer_beeps)
        led = st.checkbox("LED Enabled", config.led_enabled)
        
        if duration != config.buzzer_duration_s or beeps != config.buzzer_beeps or led != config.led_enabled:
            save_config(AlarmConfig(duration, beeps, 1.0, led))
    except Exception as e:
        st.error(f"Config error: {e}")

# Auto-refresh
if auto_refresh:
    time.sleep(float(refresh_s))
    st.rerun()

"""Streamlit UI for visualizing sensor data stored in PostgreSQL.

Run:
    streamlit run user_interface/app.py

The UI reads from the DB via db_interfaces/*_db.py.
Styled to match InnoMine professional mining dashboard.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

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
    page_title="InnoMine — Sensor Dashboard",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Custom CSS - InnoMine Dark Theme
# ============================================================================
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    /* Root variables */
    :root {
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-tertiary: #334155;
        --bg-card: #1e293b;
        --border-color: rgba(255, 255, 255, 0.1);
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent-blue: #3b82f6;
        --accent-green: #10b981;
        --accent-yellow: #f59e0b;
        --accent-red: #ef4444;
        --status-safe: #10b981;
        --status-warning: #f59e0b;
        --status-danger: #ef4444;
    }
    
    /* Main app styling */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header styling */
    .main-header {
        background: rgba(30, 41, 59, 0.95);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1rem 2rem;
        margin: -1rem -1rem 2rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .brand-title {
        font-size: 1.75rem;
        font-weight: 800;
        color: #f1f5f9;
        letter-spacing: -0.025em;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .clock-display {
        font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
        font-size: 0.875rem;
        color: #94a3b8;
        font-weight: 500;
    }
    
    /* Stat cards */
    .stat-card {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        transition: all 0.2s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.16);
    }
    
    .stat-icon {
        font-size: 2rem;
        opacity: 0.8;
    }
    
    .stat-value {
        font-size: 2.5rem;
        font-weight: 800;
        line-height: 1;
        color: #f1f5f9;
        margin-bottom: 0.25rem;
    }
    
    .stat-label {
        font-size: 0.875rem;
        color: #94a3b8;
        font-weight: 500;
    }
    
    /* Sensor cards */
    .sensor-card {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .sensor-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: #10b981;
    }
    
    .sensor-card.warning::before {
        background: #f59e0b;
    }
    
    .sensor-card.danger::before {
        background: #ef4444;
    }
    
    .sensor-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
        border-color: rgba(59, 130, 246, 0.3);
    }
    
    /* Status badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .status-badge.normal {
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
    }
    
    .status-badge.warning {
        background: rgba(245, 158, 11, 0.1);
        color: #f59e0b;
    }
    
    .status-badge.danger {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* Metric cards */
    .metric-card {
        background: #334155;
        border-radius: 8px;
        padding: 1rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .metric-icon {
        font-size: 1.5rem;
        opacity: 0.8;
    }
    
    .metric-value {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    
    /* Insights panel */
    .insights-panel {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
    }
    
    .insight-item {
        background: #334155;
        border-radius: 8px;
        padding: 1rem;
        border-left: 4px solid #10b981;
        margin-bottom: 0.75rem;
    }
    
    .insight-item.warning {
        border-left-color: #f59e0b;
    }
    
    .insight-item.danger {
        border-left-color: #ef4444;
    }
    
    .insight-priority {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.875rem;
        font-weight: 600;
        margin-bottom: 0.25rem;
    }
    
    .priority-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: currentColor;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Override Streamlit defaults */
    .stMetric {
        background: #1e293b;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .stMetric label {
        color: #94a3b8 !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #1e293b;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #f1f5f9;
    }
    
    /* Fix text colors */
    .stMarkdown, .stText, p, span, label {
        color: #f1f5f9;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f1f5f9 !important;
    }
    
    /* Divider */
    hr {
        border-color: rgba(255, 255, 255, 0.1);
    }
    
    /* Charts */
    .stAltairChart {
        background: #1e293b;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Thresholds (matching alarm_worker.py)
# ============================================================================
THRESHOLDS = {
    "temp_c_critical": 38.0,  # Human body fever threshold
    "co2_ppm_critical": 1000,  # Soda can CO2 detection
    "humidity_rh_critical": 85,  # High humidity
    "temp_c_warning": 37.0,
    "co2_ppm_warning": 800,
    "humidity_rh_warning": 70,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_status(value: float, metric: str) -> str:
    """Get status level based on thresholds."""
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
    return "normal"


def get_status_emoji(status: str) -> str:
    return {"normal": "🟢", "warning": "🟡", "danger": "🔴"}.get(status, "⚪")


# ============================================================================
# Header
# ============================================================================
st.markdown("""
<div class="main-header">
    <h1 class="brand-title">⛏️ InnoMine</h1>
    <div class="clock-display">""" + datetime.now().strftime('%H:%M:%S') + """</div>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# Sidebar Controls
# ============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    
    dataset = st.selectbox(
        "📊 Dataset",
        ["SCD40 (CO₂/Temp/Humidity)", "DS18B20 (Temperature)", "MPU6050 (Motion)", "Alarms"],
        index=0,
        key="dataset",
    )
    
    st.divider()
    
    limit = st.slider("📈 Rows to load", min_value=50, max_value=5000, value=500, step=50)
    lookback_h = st.slider(
        "⏰ Lookback (hours)",
        min_value=1,
        max_value=48,
        value=6,
        step=1,
        help="Dashboard queries only rows newer than now - lookback.",
    )
    
    st.divider()
    
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
    refresh_s = st.slider(
        "Refresh interval (seconds)", min_value=1, max_value=30, value=2, step=1
    )
    
    st.divider()
    
    st.markdown("### 🚨 Alarm Thresholds")
    st.markdown(f"""
    - **Temperature**: {THRESHOLDS['temp_c_critical']}°C (critical)
    - **CO₂**: {THRESHOLDS['co2_ppm_critical']} ppm (critical)
    - **Humidity**: {THRESHOLDS['humidity_rh_critical']}% (critical)
    """)


# ============================================================================
# Helper Functions
# ============================================================================
def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.sort_values("recorded_at")
    return df


def _show_simulated_banner(df: pd.DataFrame) -> None:
    if df.empty or "is_simulated" not in df.columns:
        return
    simulated_count = int(df["is_simulated"].fillna(False).sum())
    if simulated_count > 0:
        st.warning(
            f"⚠️ Some readings are SIMULATED (device missing). Rows simulated: {simulated_count}."
        )


def _line_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str = "#10b981"):
    """Create a styled line chart."""
    line = alt.Chart(df).mark_line(strokeWidth=4, color=color).encode(
        x=alt.X(x, title="Time", axis=alt.Axis(labelColor="#94a3b8", titleColor="#f1f5f9")),
        y=alt.Y(y, title=y, scale=alt.Scale(zero=False), axis=alt.Axis(labelColor="#94a3b8", titleColor="#f1f5f9")),
    )
    points = alt.Chart(df).mark_circle(size=60, color=color).encode(
        x=alt.X(x),
        y=alt.Y(y),
        tooltip=[x, y],
    )
    c = (line + points).properties(
        title=alt.TitleParams(text=title, color="#f1f5f9", fontSize=16, fontWeight="bold"),
        height=350,
        background="#1e293b",
    ).configure_view(
        strokeWidth=0,
    ).interactive()
    st.altair_chart(c, use_container_width=True)


def render_stat_cards(stats: list):
    """Render statistics cards."""
    cols = st.columns(len(stats))
    for col, stat in zip(cols, stats):
        with col:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-icon">{stat['icon']}</div>
                <div>
                    <div class="stat-value">{stat['value']}</div>
                    <div class="stat-label">{stat['label']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_insights(alerts: list):
    """Render AI insights panel."""
    st.markdown('<div class="section-header">🤖 AI Insights & Recommendations</div>', unsafe_allow_html=True)
    
    if not alerts:
        st.markdown("""
        <div class="insight-item">
            <div class="insight-priority" style="color: #10b981;">
                <span class="priority-dot"></span>
                <span>All Systems Normal</span>
            </div>
            <p style="color: #94a3b8; margin: 0;">All sensors operating within safe parameters. Continue standard monitoring.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for alert in alerts[:3]:
            status_class = alert.get("status", "warning")
            st.markdown(f"""
            <div class="insight-item {status_class}">
                <div class="insight-priority" style="color: {'#ef4444' if status_class == 'danger' else '#f59e0b'};">
                    <span class="priority-dot"></span>
                    <span>{alert['title']}</span>
                </div>
                <p style="color: #94a3b8; margin: 0;">{alert['message']}</p>
            </div>
            """, unsafe_allow_html=True)


# ============================================================================
# Sensor Views
# ============================================================================
def show_scd40():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_scd40(limit=limit, since=since)
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("📭 No SCD40 data yet.")
        return

    df = _prepare(df)
    _show_simulated_banner(df)
    
    latest = df.iloc[-1]
    
    # Determine statuses
    co2_status = get_status(latest['co2_ppm'], "co2_ppm")
    temp_status = get_status(latest['temperature_c'], "temperature_c")
    hum_status = get_status(latest['humidity_rh'], "humidity_rh")
    
    # Overall status
    statuses = [co2_status, temp_status, hum_status]
    overall = "danger" if "danger" in statuses else ("warning" if "warning" in statuses else "normal")
    
    # Stats bar
    render_stat_cards([
        {"icon": "💨", "value": f"{latest['co2_ppm']:.0f}", "label": "CO₂ (ppm)"},
        {"icon": "🌡️", "value": f"{latest['temperature_c']:.1f}°C", "label": "Temperature"},
        {"icon": "💧", "value": f"{latest['humidity_rh']:.1f}%", "label": "Humidity"},
        {"icon": get_status_emoji(overall), "value": overall.upper(), "label": "Status"},
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Charts
    col1, col2 = st.columns(2)
    with col1:
        color = "#ef4444" if co2_status == "danger" else ("#f59e0b" if co2_status == "warning" else "#10b981")
        _line_chart(df, "recorded_at", "co2_ppm", "CO₂ Concentration (ppm)", color)
    with col2:
        color = "#ef4444" if temp_status == "danger" else ("#f59e0b" if temp_status == "warning" else "#3b82f6")
        _line_chart(df, "recorded_at", "temperature_c", "Temperature (°C)", color)
    
    col3, col4 = st.columns(2)
    with col3:
        color = "#ef4444" if hum_status == "danger" else ("#f59e0b" if hum_status == "warning" else "#06b6d4")
        _line_chart(df, "recorded_at", "humidity_rh", "Humidity (%RH)", color)
    with col4:
        # Generate insights
        alerts = []
        if co2_status == "danger":
            alerts.append({"status": "danger", "title": "CO₂ Critical", "message": f"CO₂ at {latest['co2_ppm']:.0f} ppm exceeds {THRESHOLDS['co2_ppm_critical']} ppm threshold. Check ventilation."})
        if temp_status == "danger":
            alerts.append({"status": "danger", "title": "Temperature Critical", "message": f"Temperature at {latest['temperature_c']:.1f}°C exceeds {THRESHOLDS['temp_c_critical']}°C threshold. Heat stress risk."})
        if hum_status == "danger":
            alerts.append({"status": "danger", "title": "Humidity Critical", "message": f"Humidity at {latest['humidity_rh']:.1f}% exceeds {THRESHOLDS['humidity_rh_critical']}% threshold."})
        if co2_status == "warning":
            alerts.append({"status": "warning", "title": "Elevated CO₂", "message": f"CO₂ at {latest['co2_ppm']:.0f} ppm - approaching critical levels."})
        if temp_status == "warning":
            alerts.append({"status": "warning", "title": "Elevated Temperature", "message": f"Temperature at {latest['temperature_c']:.1f}°C - monitor closely."})
        
        render_insights(alerts)
    
    st.divider()
    st.markdown('<div class="section-header">📋 Recent Data</div>', unsafe_allow_html=True)
    st.dataframe(df.tail(50), use_container_width=True)


def show_ds18b20():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_ds18b20(limit=limit, since=since)
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("📭 No DS18B20 data yet.")
        return

    df = df.rename(columns={"celsius": "temperature_c", "fahrenheit": "temperature_f"})
    df = _prepare(df)
    _show_simulated_banner(df)
    
    latest = df.iloc[-1]
    temp_status = get_status(latest['temperature_c'], "temperature_c")
    
    render_stat_cards([
        {"icon": "🌡️", "value": f"{latest['temperature_c']:.1f}°C", "label": "Temperature (C)"},
        {"icon": "🌡️", "value": f"{latest['temperature_f']:.1f}°F", "label": "Temperature (F)"},
        {"icon": get_status_emoji(temp_status), "value": temp_status.upper(), "label": "Status"},
        {"icon": "🕐", "value": latest['recorded_at'].strftime('%H:%M:%S'), "label": "Last Reading"},
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    color = "#ef4444" if temp_status == "danger" else ("#f59e0b" if temp_status == "warning" else "#3b82f6")
    _line_chart(df, "recorded_at", "temperature_c", "DS18B20 Temperature (°C)", color)
    
    alerts = []
    if temp_status == "danger":
        alerts.append({"status": "danger", "title": "Temperature Critical", "message": f"Temperature at {latest['temperature_c']:.1f}°C exceeds threshold."})
    elif temp_status == "warning":
        alerts.append({"status": "warning", "title": "Elevated Temperature", "message": f"Temperature at {latest['temperature_c']:.1f}°C - monitor closely."})
    render_insights(alerts)
    
    st.divider()
    st.markdown('<div class="section-header">📋 Recent Data</div>', unsafe_allow_html=True)
    st.dataframe(df.tail(50), use_container_width=True)


def show_mpu6050():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_mpu6050(limit=limit, since=since)
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.info("📭 No MPU6050 data yet.")
        return

    df = _prepare(df)
    _show_simulated_banner(df)
    
    latest = df.iloc[-1]
    
    render_stat_cards([
        {"icon": "📐", "value": f"{latest['accel_x_g']:.3f}g", "label": "Accel X"},
        {"icon": "📐", "value": f"{latest['accel_y_g']:.3f}g", "label": "Accel Y"},
        {"icon": "📐", "value": f"{latest['accel_z_g']:.3f}g", "label": "Accel Z"},
        {"icon": "🌡️", "value": f"{latest['temperature_c']:.1f}°C", "label": "Temperature"},
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        axis = st.selectbox("Accel axis", ["accel_x_g", "accel_y_g", "accel_z_g"], key="mpu_accel")
        _line_chart(df, "recorded_at", axis, f"Acceleration ({axis})", "#8b5cf6")
    with col2:
        axis = st.selectbox("Gyro axis", ["gyro_x_dps", "gyro_y_dps", "gyro_z_dps"], key="mpu_gyro")
        _line_chart(df, "recorded_at", axis, f"Gyroscope ({axis})", "#ec4899")
    
    render_insights([])
    
    st.divider()
    st.markdown('<div class="section-header">📋 Recent Data</div>', unsafe_allow_html=True)
    st.dataframe(df.tail(50), use_container_width=True)


def show_alarms():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_alarms(limit=min(limit, 500), since=since)
    df = pd.DataFrame(rows)
    
    alarm_count = len(df) if not df.empty else 0
    
    render_stat_cards([
        {"icon": "🚨", "value": str(alarm_count), "label": "Total Alarms"},
        {"icon": "⏰", "value": f"{lookback_h}h", "label": "Time Window"},
        {"icon": "🔴" if alarm_count > 0 else "🟢", "value": "ACTIVE" if alarm_count > 0 else "CLEAR", "label": "Alert Status"},
    ])
    
    if df.empty:
        st.info("✅ No alarms in the selected time window.")
        render_insights([])
        return

    df = df.sort_values("triggered_at")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">🚨 Alarm Events</div>', unsafe_allow_html=True)
    st.dataframe(df.tail(200), use_container_width=True)

    if "metric" in df.columns:
        metric = st.selectbox(
            "Filter by Metric",
            sorted(df["metric"].dropna().unique().tolist()),
            key="alarm_metric",
        )
        sub = df[df["metric"] == metric]
        if not sub.empty and "value" in sub.columns:
            c = (
                alt.Chart(sub)
                .mark_line(strokeWidth=4, color="#ef4444")
                .encode(
                    x=alt.X("triggered_at", title="Time"),
                    y=alt.Y("value", title="Value"),
                    color=alt.Color("sensor", title="Sensor"),
                )
                .properties(title=f"Alarm Values: {metric}", height=350)
                .interactive()
            )
            st.altair_chart(c, use_container_width=True)


# ============================================================================
# Main Routing
# ============================================================================
if "SCD40" in dataset:
    show_scd40()
elif "DS18B20" in dataset:
    show_ds18b20()
elif "MPU6050" in dataset:
    show_mpu6050()
else:
    show_alarms()


# ============================================================================
# Auto-refresh
# ============================================================================
if auto_refresh:
    time.sleep(float(refresh_s))
    st.rerun()

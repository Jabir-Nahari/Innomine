"""Streamlit UI for visualizing sensor data stored in PostgreSQL.

Run:
    streamlit run user_interface/app.py

The UI reads from the DB via db_interfaces/*_db.py.
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


st.set_page_config(page_title="Innomine Sensors", layout="wide")

# Show last updated timestamp
st.title("Innomine – Sensor Dashboard")
st.caption(f"🕐 Last updated: {datetime.now().strftime('%H:%M:%S')}")

with st.sidebar:
    st.header("Controls")
    dataset = st.selectbox(
        "Dataset",
        ["SCD40", "DS18B20", "MPU6050", "Alarms"],
        index=0,
        key="dataset",
    )
    limit = st.slider("Rows to load", min_value=50, max_value=5000, value=500, step=50)
    lookback_h = st.slider(
        "Lookback window (hours)",
        min_value=1,
        max_value=48,
        value=6,
        step=1,
        help="Dashboard queries only rows newer than now - lookback.",
    )
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_s = st.slider(
        "Refresh interval (seconds)", min_value=1, max_value=30, value=2, step=1
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _line_chart(df: pd.DataFrame, x: str, y: str, title: str):
    """Create a line chart with thicker lines and visible data points."""
    line = alt.Chart(df).mark_line(strokeWidth=4, color="#4CAF50").encode(
        x=alt.X(x, title="Time"),
        y=alt.Y(y, title=y, scale=alt.Scale(zero=False)),
    )
    points = alt.Chart(df).mark_circle(size=60, color="#2E7D32").encode(
        x=alt.X(x),
        y=alt.Y(y),
        tooltip=[x, y],
    )
    c = (line + points).properties(title=title, height=400).interactive()
    st.altair_chart(c, use_container_width=True)


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
            f"Some readings are SIMULATED (device missing or read failure). Rows simulated: {simulated_count}."
        )


def show_scd40():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_scd40(limit=limit, since=since)
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No SCD40 data yet.")
        return

    df = _prepare(df)
    _show_simulated_banner(df)

    # Show latest values as metrics
    latest = df.iloc[-1] if not df.empty else None
    if latest is not None:
        st.subheader("📊 Current Readings")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("CO₂", f"{latest['co2_ppm']:.0f} ppm")
        m2.metric("Temperature", f"{latest['temperature_c']:.1f} °C")
        m3.metric("Humidity", f"{latest['humidity_rh']:.1f} %RH")
        m4.metric("Last Reading", latest['recorded_at'].strftime('%H:%M:%S'))
        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        _line_chart(df, "recorded_at", "co2_ppm", "CO2 (ppm)")
        _line_chart(df, "recorded_at", "humidity_rh", "Humidity (%RH)")
    with col2:
        unit = st.selectbox(
            "Temperature unit",
            ["temperature_c", "temperature_f"],
            index=0,
            key="scd40_temp_unit",
        )
        _line_chart(df, "recorded_at", unit, f"Temperature ({unit})")

    st.subheader("Latest rows")
    st.dataframe(df.tail(50), use_container_width=True)


def show_ds18b20():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_ds18b20(limit=limit, since=since)
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No DS18B20 data yet.")
        return

    df = df.rename(columns={"celsius": "temperature_c", "fahrenheit": "temperature_f"})
    df = _prepare(df)
    _show_simulated_banner(df)

    # Show latest values as metrics
    latest = df.iloc[-1] if not df.empty else None
    if latest is not None:
        st.subheader("📊 Current Readings")
        m1, m2, m3 = st.columns(3)
        m1.metric("Temperature", f"{latest['temperature_c']:.1f} °C")
        m2.metric("Fahrenheit", f"{latest['temperature_f']:.1f} °F")
        m3.metric("Last Reading", latest['recorded_at'].strftime('%H:%M:%S'))
        st.divider()

    unit = st.selectbox(
        "Temperature unit",
        ["temperature_c", "temperature_f"],
        index=0,
        key="ds18b20_temp_unit",
    )
    _line_chart(df, "recorded_at", unit, f"DS18B20 Temperature ({unit})")

    st.subheader("Latest rows")
    st.dataframe(df.tail(50), use_container_width=True)


def show_mpu6050():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_mpu6050(limit=limit, since=since)
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No MPU6050 data yet.")
        return

    df = _prepare(df)
    _show_simulated_banner(df)

    # Show latest values as metrics
    latest = df.iloc[-1] if not df.empty else None
    if latest is not None:
        st.subheader("📊 Current Readings")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Accel X", f"{latest['accel_x_g']:.3f} g")
        m2.metric("Accel Y", f"{latest['accel_y_g']:.3f} g")
        m3.metric("Accel Z", f"{latest['accel_z_g']:.3f} g")
        m4.metric("Temperature", f"{latest['temperature_c']:.1f} °C")
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("Gyro X", f"{latest['gyro_x_dps']:.1f} °/s")
        m6.metric("Gyro Y", f"{latest['gyro_y_dps']:.1f} °/s")
        m7.metric("Gyro Z", f"{latest['gyro_z_dps']:.1f} °/s")
        m8.metric("Last Reading", latest['recorded_at'].strftime('%H:%M:%S'))
        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        axis = st.selectbox(
            "Accel axis",
            ["accel_x_g", "accel_y_g", "accel_z_g"],
            index=0,
            key="mpu_accel_axis",
        )
        _line_chart(df, "recorded_at", axis, f"Acceleration ({axis})")

    with col2:
        axis = st.selectbox(
            "Gyro axis",
            ["gyro_x_dps", "gyro_y_dps", "gyro_z_dps"],
            index=0,
            key="mpu_gyro_axis",
        )
        _line_chart(df, "recorded_at", axis, f"Gyroscope ({axis})")

    unit = st.selectbox(
        "MPU temperature unit",
        ["temperature_c", "temperature_f"],
        index=0,
        key="mpu_temp_unit",
    )
    _line_chart(df, "recorded_at", unit, f"MPU6050 Temperature ({unit})")

    st.subheader("Latest rows")
    st.dataframe(df.tail(50), use_container_width=True)


def show_alarms():
    since = _utc_now() - timedelta(hours=int(lookback_h))
    rows = fetch_recent_alarms(limit=min(limit, 500), since=since)
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No alarms yet.")
        return

    df = df.sort_values("triggered_at")

    st.subheader("Alarm events")
    st.dataframe(df.tail(200), use_container_width=True)

    if "metric" in df.columns:
        metric = st.selectbox(
            "Metric",
            sorted(df["metric"].dropna().unique().tolist()),
            key="alarm_metric",
        )
        sub = df[df["metric"] == metric]
        if not sub.empty and "value" in sub.columns:
            c = (
                alt.Chart(sub)
                .mark_line(strokeWidth=3)
                .encode(
                    x=alt.X("triggered_at", title="Time"),
                    y=alt.Y("value", title="Value"),
                    color=alt.Color("sensor", title="Sensor"),
                )
                .properties(title=f"Alarms: {metric}", height=360)
            )
            st.altair_chart(c, use_container_width=True)


if dataset == "SCD40":
    show_scd40()
elif dataset == "DS18B20":
    show_ds18b20()
elif dataset == "MPU6050":
    show_mpu6050()
else:
    show_alarms()

if auto_refresh:
    time.sleep(float(refresh_s))
    st.rerun()

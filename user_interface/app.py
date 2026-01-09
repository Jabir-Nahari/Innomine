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

st.title("Innomine – Sensor Dashboard")

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
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    refresh_s = st.slider(
        "Refresh interval (seconds)", min_value=1, max_value=30, value=5, step=1
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _line_chart(df: pd.DataFrame, x: str, y: str, title: str):
    c = (
        alt.Chart(df)
        .mark_line(strokeWidth=3)
        .encode(x=alt.X(x, title="Time"), y=alt.Y(y, title=y))
        .properties(title=title, height=360)
    )
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

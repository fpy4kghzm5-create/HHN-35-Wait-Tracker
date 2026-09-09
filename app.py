import csv
import io
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "hhn_wait_times.db"
TZ = ZoneInfo("America/New_York")
API_URL = "https://queue-times.com/parks/65/queue_times.json"

# Update these names if Queue-Times uses slightly different attraction names.
HOUSE_MATCHES = {
    "Jack & Oddfellow": ["Jack & Oddfellow"],
    "Sinners": ["Sinners"],
    "Stranger Things 5": ["Stranger Things 5"],
    "Hellraiser": ["Hellraiser"],
    "Ozzy Osbourne": ["Ozzy Osbourne"],
    "Evil Dead Burn": ["Evil Dead Burn"],
    "H.R. Bloodengutz": ["H.R. Bloodengutz"],
    "MADLANDS": ["MADLANDS"],
    "INVASION": ["INVASION"],
    "Cybergoria": ["Cybergoria"],
}

st.set_page_config(
    page_title="HHN 35 Wait-Time Tracker",
    page_icon="🎃",
    layout="wide",
)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS waits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            house TEXT NOT NULL,
            wait_minutes INTEGER,
            is_open INTEGER NOT NULL,
            source_updated_at TEXT
        )
    """)
    conn.commit()
    return conn

def fetch_queue_times():
    r = requests.get(API_URL, timeout=20)
    r.raise_for_status()
    return r.json()

def normalize_name(name):
    return " ".join(str(name).lower().replace(":", " ").split())

def find_houses(payload):
    rides = []
    for land in payload.get("lands", []):
        for ride in land.get("rides", []):
            rides.append(ride)

    results = {}
    for label, patterns in HOUSE_MATCHES.items():
        for ride in rides:
            n = normalize_name(ride.get("name", ""))
            if any(normalize_name(p) in n for p in patterns):
                results[label] = ride
                break
    return results

def collect_snapshot():
    payload = fetch_queue_times()
    matches = find_houses(payload)
    now = datetime.now(TZ).isoformat(timespec="seconds")

    conn = db()
    rows = []
    for house in HOUSE_MATCHES:
        ride = matches.get(house)
        if ride is None:
            rows.append((now, house, None, 0, None))
        else:
            wait = ride.get("wait_time")
            is_open = int(bool(ride.get("is_open")))
            source_updated = ride.get("last_updated")
            rows.append((now, house, wait, is_open, source_updated))

    conn.executemany("""
        INSERT INTO waits
        (recorded_at, house, wait_minutes, is_open, source_updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()
    return len(matches)

def load_data():
    conn = db()
    df = pd.read_sql_query(
        "SELECT recorded_at, house, wait_minutes, is_open, source_updated_at FROM waits ORDER BY recorded_at",
        conn,
    )
    conn.close()
    if not df.empty:
        df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    return df

def export_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def export_xlsx(df):
    out = io.BytesIO()

    # Excel/openpyxl does not support timezone-aware datetimes.
    # Keep the displayed timestamps intact by exporting them as text.
    excel_df = df.copy()
    if "recorded_at" in excel_df.columns:
        excel_df["recorded_at"] = excel_df["recorded_at"].astype(str)

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        excel_df.to_excel(writer, index=False, sheet_name="Wait Times")
        summary = (
            df.dropna(subset=["wait_minutes"])
              .groupby("house")["wait_minutes"]
              .agg(["count", "mean", "min", "max"])
              .reset_index()
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")
    return out.getvalue()

st.title("🎃 Halloween Horror Nights 35")
st.caption("Universal Orlando • 10-minute wait-time tracker")

with st.sidebar:
    st.header("Controls")
    if st.button("📡 Record snapshot now", use_container_width=True):
        try:
            count = collect_snapshot()
            st.success(f"Recorded {count} matched houses.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not collect data: {e}")

    st.markdown("### Automatic collection")
    st.write(
        "The included collector script records a snapshot every 10 minutes. "
        "Keep it running during HHN to build the night's history."
    )

    df = load_data()
    if not df.empty:
        st.download_button(
            "⬇️ Export CSV",
            export_csv(df),
            file_name="HHN_35_wait_times.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "📊 Export Excel",
            export_xlsx(df),
            file_name="HHN_35_wait_times.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

df = load_data()

if df.empty:
    st.info("No snapshots yet. Click **Record snapshot now** or start the 10-minute collector.")
else:
    latest_time = df["recorded_at"].max()
    latest = df[df["recorded_at"] == latest_time].copy()

    st.subheader(f"Latest snapshot • {latest_time.strftime('%I:%M %p')}")

    cols = st.columns(5)
    for i, house in enumerate(HOUSE_MATCHES):
        row = latest[latest["house"] == house]
        with cols[i % 5]:
            st.metric(
                house,
                "N/A" if row.empty or pd.isna(row.iloc[0]["wait_minutes"])
                else f"{int(row.iloc[0]['wait_minutes'])} min",
                "Open" if not row.empty and row.iloc[0]["is_open"] else "Closed / unavailable",
            )

    st.subheader("Wait times over time")
    pivot = df.pivot_table(
        index="recorded_at",
        columns="house",
        values="wait_minutes",
        aggfunc="last",
    ).sort_index()
    st.line_chart(pivot, height=500)

    st.subheader("House summary")
    summary = (
        df.dropna(subset=["wait_minutes"])
          .groupby("house")["wait_minutes"]
          .agg(
              Samples="count",
              Average="mean",
              Minimum="min",
              Maximum="max",
          )
          .round(1)
          .sort_values("Average", ascending=False)
    )
    st.dataframe(summary, use_container_width=True)

    st.subheader("Raw data")
    st.dataframe(df.sort_values("recorded_at", ascending=False), use_container_width=True)

st.divider()
st.caption("Powered by Queue-Times.com. Verify current API terms/attribution before deploying publicly.")

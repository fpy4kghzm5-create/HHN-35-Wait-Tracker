import io
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

TZ = ZoneInfo("America/New_York")

# IMPORTANT: After creating your GitHub repository, replace YOUR_USERNAME below.
REPO = "fpy4kghzm5-create/HHN-35-Wait-Tracker"
BRANCH = "main"
DATA_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/waits.csv"

HOUSES = [
    "Cybergoria", "Evil Dead Burn", "H.R. Bloodengutz", "Hellraiser",
    "INVASION", "Jack & Oddfellow", "MADLANDS", "Ozzy Osbourne",
    "Sinners", "Stranger Things 5"
]

st.set_page_config(page_title="HHN 35 Wait Times", page_icon="🎃", layout="wide")

@st.cache_data(ttl=30)
def load_data():
    try:
        df = pd.read_csv(DATA_URL)
        if df.empty:
            return df
        df["recorded_at"] = pd.to_datetime(df["recorded_at"], errors="coerce")
        df["wait_minutes"] = pd.to_numeric(df["wait_minutes"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame(columns=["recorded_at", "house", "wait_minutes", "status"])

def excel_bytes(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wait Times")
        summary = (
            df.dropna(subset=["wait_minutes"])
            .groupby("house")["wait_minutes"]
            .agg(Samples="count", Average="mean", Minimum="min", Maximum="max")
            .round(1).reset_index()
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")
    return out.getvalue()

st.title("🎃 HHN 35 Wait Times")
st.caption("Universal Orlando • Automatic 10-minute tracking")

df = load_data()

if df.empty:
    st.warning("No wait-time data has been collected yet. Check the GitHub Actions workflow.")
    st.stop()

latest_time = df["recorded_at"].max()
latest = df[df["recorded_at"] == latest_time].copy()

st.markdown(f"### Live waits · {latest_time.strftime('%I:%M %p') if pd.notna(latest_time) else '—'}")

# Sort current houses by wait, longest first.
cards = []
for house in HOUSES:
    row = latest[latest["house"] == house]
    if row.empty:
        cards.append((house, None, "Not found"))
    else:
        r = row.iloc[0]
        wait = None if pd.isna(r["wait_minutes"]) else int(r["wait_minutes"])
        cards.append((house, wait, str(r.get("status", ""))))

for start in range(0, len(cards), 5):
    cols = st.columns(5)
    for col, (house, wait, status) in zip(cols, cards[start:start+5]):
        with col:
            st.metric(house, f"{wait} min" if wait is not None else status)

st.divider()

st.subheader("📈 Wait times tonight")
pivot = (
    df.pivot_table(index="recorded_at", columns="house", values="wait_minutes", aggfunc="last")
    .sort_index()
)
st.line_chart(pivot, height=500)

st.subheader("🔥 House rankings")
summary = (
    df.dropna(subset=["wait_minutes"])
    .groupby("house")["wait_minutes"]
    .agg(Samples="count", Average="mean", Minimum="min", Maximum="max")
    .round(1)
    .sort_values("Average", ascending=False)
)
st.dataframe(summary, use_container_width=True)

st.subheader("📥 Export")
c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode(),
        "HHN_35_wait_times.csv",
        "text/csv",
        use_container_width=True,
    )
with c2:
    st.download_button(
        "Download Excel",
        excel_bytes(df),
        "HHN_35_wait_times.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.caption("Data is collected by GitHub Actions every 10 minutes and stored in this project's GitHub repository.")

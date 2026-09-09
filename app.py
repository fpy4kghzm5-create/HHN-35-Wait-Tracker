import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

TZ = ZoneInfo("America/New_York")

REPO = "fpy4kghzm5-create/HHN-35-Wait-Tracker"
BRANCH = "main"
DATA_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/waits.csv"

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

HOUSES = list(HOUSE_MATCHES.keys())
CLOSED_WEEKDAYS = {0, 1}  # Monday and Tuesday
AFTER_MIDNIGHT_CUTOFF_HOUR = 6


st.set_page_config(
    page_title="HHN 35 Wait-Time Tracker",
    page_icon="🎃",
    layout="wide",
)


def event_date_for(dt):
    """Assign after-midnight records (before 6 AM) to the previous HHN night."""
    local_dt = dt.astimezone(TZ) if dt.tzinfo else dt.replace(tzinfo=TZ)
    if local_dt.hour < AFTER_MIDNIGHT_CUTOFF_HOUR:
        local_dt = local_dt - timedelta(days=1)
    return local_dt.date().isoformat()


def today_local():
    return datetime.now(TZ)


def tonight_event_date():
    return event_date_for(today_local())


def is_closed_today():
    return today_local().weekday() in CLOSED_WEEKDAYS


@st.cache_data(ttl=30)
def load_data():
    columns = ["recorded_at", "event_date", "house", "wait_minutes", "status"]
    try:
        df = pd.read_csv(DATA_URL)
    except Exception:
        return pd.DataFrame(columns=columns)

    if df.empty:
        return pd.DataFrame(columns=columns)

    # Support the older four-column CSV while it is being phased out.
    if "status" not in df.columns:
        df["status"] = ""
    if "event_date" not in df.columns:
        parsed = pd.to_datetime(df["recorded_at"], errors="coerce")
        df["event_date"] = [
            event_date_for(x.to_pydatetime()) if pd.notna(x) else ""
            for x in parsed
        ]

    df["recorded_at"] = pd.to_datetime(df["recorded_at"], errors="coerce")
    df["wait_minutes"] = pd.to_numeric(df["wait_minutes"], errors="coerce")
    df["event_date"] = df["event_date"].astype(str)

    # Monday/Tuesday should never be treated as HHN operating-night data.
    parsed_event = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[parsed_event.dt.weekday.isin([2, 3, 4, 5, 6])].copy()

    return df[columns].sort_values("recorded_at")


def export_csv(df):
    return df.to_csv(index=False).encode("utf-8")


def export_xlsx(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wait Times")
        summary = (
            df.dropna(subset=["wait_minutes"])
            .groupby("house")["wait_minutes"]
            .agg(["count", "mean", "min", "max"])
            .reset_index()
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")
    return out.getvalue()


def format_date(value):
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return "—"
    return dt.strftime("%B %d, %Y").replace(" 0", " ")


st.title("🎃 Halloween Horror Nights 35")
st.caption("Universal Orlando • 10-minute wait-time tracker")

df = load_data()

with st.sidebar:
    st.header("Controls")

    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("### Automatic collection")
    st.write(
        "GitHub Actions collects a snapshot every 10 minutes while HHN is operating. "
        "Monday and Tuesday are treated as closed nights, and records after midnight "
        "until 6:00 AM remain part of the previous night's data."
    )

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


if df.empty:
    st.info("No snapshots yet. The automatic collector will add data when HHN is operating.")
else:
    now = today_local()
    tonight = tonight_event_date()

    # Never display an old operating-night snapshot as if it were live on a closed day.
    if is_closed_today():
        st.warning(
            f"🎃 **HHN is closed tonight.** There are no live wait times to display for "
            f"{format_date(now.date())}. Historical wait-time data is still available below."
        )
        latest_time = None
        latest = pd.DataFrame()
    else:
        tonight_rows = df[df["event_date"] == tonight].copy()
        if tonight_rows.empty:
            st.info(
                f"🎃 **HHN is not collecting wait times yet for {format_date(tonight)}.** "
                "Tonight's data will appear automatically when the collector runs."
            )
            latest_time = None
            latest = pd.DataFrame()
        else:
            latest_time = tonight_rows["recorded_at"].max()
            latest = tonight_rows[tonight_rows["recorded_at"] == latest_time].copy()
            st.subheader(
                f"Latest snapshot • {latest_time.strftime('%I:%M %p').lstrip('0')}"
            )

            cols = st.columns(5)
            for i, house in enumerate(HOUSE_MATCHES):
                row = latest[latest["house"] == house]
                with cols[i % 5]:
                    if row.empty:
                        value = "N/A"
                        delta = "No data"
                    else:
                        r = row.iloc[0]
                        value = (
                            "N/A"
                            if pd.isna(r["wait_minutes"])
                            else f"{int(r['wait_minutes'])} min"
                        )
                        delta = str(r["status"]) if str(r["status"]) else "Unknown"
                    st.metric(house, value, delta)

    st.divider()

    st.subheader("📈 Wait times over time")
    pivot = (
        df.pivot_table(
            index="recorded_at",
            columns="house",
            values="wait_minutes",
            aggfunc="last",
        )
        .sort_index()
    )
    st.line_chart(pivot, height=500)

    st.subheader("🔥 House summary")
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

    st.subheader("📥 Export")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Download CSV",
            export_csv(df),
            "HHN_35_wait_times.csv",
            "text/csv",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "Download Excel",
            export_xlsx(df),
            "HHN_35_wait_times.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.subheader("Raw data")
    st.dataframe(
        df.sort_values("recorded_at", ascending=False),
        use_container_width=True,
    )

st.divider()
st.caption(
    "Powered by Queue-Times.com. Data is collected by GitHub Actions every 10 minutes."
)

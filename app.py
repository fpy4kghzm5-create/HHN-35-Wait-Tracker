import io
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

TZ = ZoneInfo("America/New_York")

REPO = "fpy4kghzm5-create/HHN-35-Wait-Tracker"
BRANCH = "main"
DATA_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/waits.csv"

HOUSES = [
    "Cybergoria",
    "Evil Dead Burn",
    "H.R. Bloodengutz",
    "Hellraiser",
    "INVASION",
    "Jack & Oddfellow",
    "MADLANDS",
    "Ozzy Osbourne",
    "Sinners",
    "Stranger Things 5",
]

st.set_page_config(
    page_title="HHN 35 Wait Times",
    page_icon="🎃",
    layout="wide",
)

# Automatically refresh the Streamlit page every 30 seconds.
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=30_000, key="wait_tracker_refresh")
except ImportError:
    pass


@st.cache_data(ttl=30)
def load_data():
    try:
        df = pd.read_csv(DATA_URL)

        if df.empty:
            return df

        df["recorded_at"] = pd.to_datetime(
            df["recorded_at"],
            errors="coerce"
        )

        df["wait_minutes"] = pd.to_numeric(
            df["wait_minutes"],
            errors="coerce"
        )

        # Make sure status is always available.
        if "status" not in df.columns:
            df["status"] = ""

        df["status"] = (
            df["status"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        return df

    except Exception:
        return pd.DataFrame(
            columns=[
                "recorded_at",
                "house",
                "wait_minutes",
                "status",
            ]
        )


def excel_bytes(df):
    out = io.BytesIO()

    # Work with a copy so the original dataframe is not changed.
    export_df = df.copy()

    # Excel cannot store timezone-aware datetime values.
    for col in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[col]):
            try:
                export_df[col] = export_df[col].dt.tz_localize(None)
            except TypeError:
                pass

    with pd.ExcelWriter(out, engine="openpyxl") as writer:

        # Full wait-time data
        export_df.to_excel(
            writer,
            index=False,
            sheet_name="Wait Times",
        )

        # Summary data
        summary = (
            export_df
            .dropna(subset=["wait_minutes"])
            .groupby("house")["wait_minutes"]
            .agg(
                Samples="count",
                Average="mean",
                Minimum="min",
                Maximum="max",
            )
            .round(1)
            .reset_index()
        )

        summary.to_excel(
            writer,
            index=False,
            sheet_name="Summary",
        )

    return out.getvalue()


# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------

st.title("🎃 HHN 35 Wait Times")
st.caption("Universal Orlando • Automatic 5-minute tracking")

df = load_data()

if df.empty:
    st.warning(
        "No wait-time data has been collected yet. "
        "Check the GitHub Actions workflow."
    )
    st.stop()


# ---------------------------------------------------------
# CURRENT WAIT TIMES
# ---------------------------------------------------------

latest_time = df["recorded_at"].max()

latest = df[
    df["recorded_at"] == latest_time
].copy()

if pd.notna(latest_time):
    display_time = latest_time.strftime("%I:%M %p")
else:
    display_time = "—"

st.markdown(f"### Live waits · {display_time}")


# Build cards for every house.
cards = []

for house in HOUSES:

    row = latest[
        latest["house"].astype(str).str.strip() == house
    ]

    if row.empty:
        cards.append(
            (house, "Not found", "not found")
        )
        continue

    r = row.iloc[0]

    # Get wait time.
    if pd.isna(r["wait_minutes"]):
        wait = None
    else:
        wait = int(r["wait_minutes"])

    # Get status.
    status = str(
        r.get("status", "")
    ).strip().lower()

    # -----------------------------------------------------
    # IMPORTANT:
    # Status takes priority over a 0-minute wait.
    # This prevents delayed houses from showing "0 min".
    # -----------------------------------------------------

    if status in ["delayed", "delay"]:
        display_value = "Delayed"

    elif status in ["closed", "close"]:
        display_value = "Closed"

    elif wait is not None:
        display_value = f"{wait} min"

    elif status:
        display_value = status.title()

    else:
        display_value = "—"

    cards.append(
        (house, display_value, status)
    )


# Display five houses per row.
for start in range(0, len(cards), 5):

    cols = st.columns(5)

    for col, (house, display_value, status) in zip(
        cols,
        cards[start:start + 5]
    ):

        with col:

            st.metric(
                house,
                display_value
            )


st.divider()


# ---------------------------------------------------------
# WAIT TIMES TONIGHT
# ---------------------------------------------------------

st.subheader("📈 Wait times tonight")

pivot = (
    df.pivot_table(
        index="recorded_at",
        columns="house",
        values="wait_minutes",
        aggfunc="last",
    )
    .sort_index()
)

st.line_chart(
    pivot,
    height=500
)


# ---------------------------------------------------------
# HOUSE RANKINGS
# ---------------------------------------------------------

st.subheader("🔥 House rankings")

summary = (
    df
    .dropna(subset=["wait_minutes"])
    .groupby("house")["wait_minutes"]
    .agg(
        Samples="count",
        Average="mean",
        Minimum="min",
        Maximum="max",
    )
    .round(1)
    .sort_values(
        "Average",
        ascending=False
    )
)

st.dataframe(
    summary,
    use_container_width=True
)


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.caption(
    "Data is collected by GitHub Actions every 5 minutes "
    "and stored in this project's GitHub repository. "
    "The website checks for new data every 30 seconds."
)

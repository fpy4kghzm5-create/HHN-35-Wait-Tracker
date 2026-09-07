import io
from datetime import datetime, time
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

SEASON_START = datetime(2026, 8, 29, tzinfo=TZ)
SEASON_END = datetime(2026, 11, 1, 23, 59, 59, tzinfo=TZ)

OPEN_TIME = time(14, 0)
CLOSE_TIME = time(3, 0)


st.set_page_config(
    page_title="HHN 35 Wait Times",
    page_icon="🎃",
    layout="wide",
)


# ---------------------------------------------------------
# AUTOMATIC WEBSITE REFRESH
# ---------------------------------------------------------

try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(
        interval=30_000,
        key="wait_tracker_refresh"
    )

except ImportError:
    pass


# ---------------------------------------------------------
# HHN OPERATING HOURS
# ---------------------------------------------------------

def is_hhn_open(now=None):
    """
    HHN season:
        August 29, 2026 through November 1, 2026

    Daily operating window:
        2:00 PM through 2:59 AM

    At 3:00 AM the tracker considers HHN closed.
    """

    if now is None:
        now = datetime.now(TZ)

    # Check season dates.
    if now < SEASON_START or now > SEASON_END:
        return False

    current_time = now.time()

    # 2:00 PM through 11:59 PM
    if current_time >= OPEN_TIME:
        return True

    # Midnight through 2:59 AM
    if current_time < CLOSE_TIME:
        return True

    return False


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# FORMAT TIMESTAMP
# ---------------------------------------------------------

def format_timestamp(value):
    """
    Display timestamps as:
    MM/DD/YYYY H:MM AM/PM
    """

    if pd.isna(value):
        return ""

    return value.strftime(
        "%m/%d/%Y %-I:%M %p"
    )


# ---------------------------------------------------------
# EXPORT DATA
# ---------------------------------------------------------

def export_dataframe(df):

    export_df = df.copy()

    export_df["recorded_at"] = (
        export_df["recorded_at"]
        .apply(format_timestamp)
    )

    return export_df


def excel_bytes(df):

    out = io.BytesIO()

    export_df = export_dataframe(df)

    with pd.ExcelWriter(
        out,
        engine="openpyxl"
    ) as writer:

        # Full wait-time data
        export_df.to_excel(
            writer,
            index=False,
            sheet_name="Wait Times",
        )

        # Summary data
        summary = (
            df
            .dropna(
                subset=["wait_minutes"]
            )
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

st.caption(
    "Universal Orlando • Automatic 5-minute tracking"
)


# ---------------------------------------------------------
# CURRENT TIME / OPEN STATUS
# ---------------------------------------------------------

now = datetime.now(TZ)

if is_hhn_open(now):

    st.success(
        f"🎃 HHN is OPEN • "
        f"{now.strftime('%-I:%M %p')}"
    )

else:

    st.info(
        f"🔒 HHN is CLOSED • "
        f"{now.strftime('%-I:%M %p')}"
    )


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

st.subheader("🎢 Current wait times")


# Outside HHN hours, show Closed instead of the last
# recorded wait time.
if not is_hhn_open(now):

    display_time = now.strftime("%-I:%M %p")

    st.markdown(
        f"### 🔒 Live waits · Closed · {display_time}"
    )

    cards = []

    for house in HOUSES:

        cards.append(
            (house, "Closed", "closed")
        )

else:

    latest_time = df["recorded_at"].max()

    latest = df[
        df["recorded_at"] == latest_time
    ].copy()

    if pd.notna(latest_time):

        display_time = latest_time.strftime(
            "%-I:%M %p"
        )

    else:

        display_time = "—"

    st.markdown(
        f"### Live waits · {display_time}"
    )

    cards = []

    for house in HOUSES:

        row = latest[
            latest["house"]
            .astype(str)
            .str.strip()
            == house
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

            wait = int(
                r["wait_minutes"]
            )

        # Get status.
        status = str(
            r.get("status", "")
        ).strip().lower()

        # Status takes priority over wait time.
        if status in [
            "delayed",
            "delay"
        ]:

            display_value = "Delayed"

        elif status in [
            "closed",
            "close"
        ]:

            display_value = "Closed"

        elif wait is not None:

            display_value = (
                f"{wait} min"
            )

        elif status:

            display_value = status.title()

        else:

            display_value = "—"

        cards.append(
            (
                house,
                display_value,
                status
            )
        )


# ---------------------------------------------------------
# HOUSE CARDS
# ---------------------------------------------------------

for start in range(
    0,
    len(cards),
    5
):

    cols = st.columns(5)

    for col, (
        house,
        display_value,
        status
    ) in zip(
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

if is_hhn_open(now):

    pivot = (
        df
        .pivot_table(
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

else:

    st.info(
        "Wait-time history will be shown here "
        "when HHN is open."
    )


# ---------------------------------------------------------
# HOUSE RANKINGS
# ---------------------------------------------------------

st.subheader("🔥 House rankings")

summary = (
    df
    .dropna(
        subset=["wait_minutes"]
    )
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

download_df = export_dataframe(df)

c1, c2 = st.columns(2)


with c1:

    st.download_button(
        "Download CSV",
        download_df
        .to_csv(index=False)
        .encode(),
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
    "during HHN operating hours and stored in this "
    "project's GitHub repository. "
    "The website checks for new data every 30 seconds. "
    "HHN season: August 29 – November 1, 2026."
)

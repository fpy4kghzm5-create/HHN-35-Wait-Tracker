import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

TZ=ZoneInfo("America/New_York")
REPO="fpy4kghzm5-create/HHN-35-Wait-Tracker"
DATA_URL=f"https://raw.githubusercontent.com/{REPO}/main/data/waits.csv"
HOUSES=["Cybergoria","Evil Dead Burn","H.R. Bloodengutz","Hellraiser","INVASION",
        "Jack & Oddfellow","MADLANDS","Ozzy Osbourne","Sinners","Stranger Things 5"]

st.set_page_config(page_title="HHN 35 Wait Times",page_icon="🎃",layout="wide")

def event_date_for(dt):
    return (dt-timedelta(days=1)).date() if dt.hour<6 else dt.date()
def operating(d):
    return d.weekday() not in (0,1)

@st.cache_data(ttl=30)
def load_data():
    df=pd.read_csv(DATA_URL)
    if df.empty: return df
    df["recorded_at"]=pd.to_datetime(df["recorded_at"],errors="coerce")
    if "event_date" not in df.columns:
        df["event_date"]=df["recorded_at"].apply(lambda x:event_date_for(x) if pd.notna(x) else pd.NaT)
    df["event_date"]=pd.to_datetime(df["event_date"],errors="coerce").dt.date
    df["wait_minutes"]=pd.to_numeric(df["wait_minutes"],errors="coerce")
    return df.dropna(subset=["recorded_at"])

def excel_bytes(df):
    b=io.BytesIO()
    with pd.ExcelWriter(b,engine="openpyxl") as w:
        df.to_excel(w,index=False,sheet_name="Wait Times")
        df.groupby("house")["wait_minutes"].agg(["count","mean","min","max"]).round(1).to_excel(w,sheet_name="Summary")
    return b.getvalue()

st.title("🎃 Halloween Horror Nights 35")
st.caption("Wait times collected automatically every 10 minutes • Powered by Queue-Times.com")

now=datetime.now(TZ); event_date=event_date_for(now)
try: df=load_data()
except Exception as e:
    st.error(f"Unable to load wait-time data: {e}"); st.stop()

if not operating(event_date):
    st.warning(f"### 🚫 HHN is closed tonight\n\n**{event_date.strftime('%A, %B %-d, %Y')}** is not an HHN 35 event night. Wait-time collection is paused on Mondays and Tuesdays.")
    st.info("Historical operating-night data is still available below. The live dashboard will resume on the next HHN event night.")
else:
    current=df[df["event_date"]==event_date].copy()
    st.subheader(f"Live waits — {event_date.strftime('%A, %B %-d, %Y')}")
    if current.empty:
        st.info("No wait-time snapshot has been recorded yet for tonight.")
    else:
        latest_time=current["recorded_at"].max()
        latest=current[current["recorded_at"]==latest_time]
        cols=st.columns(5)
        for i,h in enumerate(HOUSES):
            m=latest[latest["house"]==h]
            val=int(m.iloc[0]["wait_minutes"]) if not m.empty else None
            cols[i%5].metric(h,f"{val} min" if val is not None else "—")
        st.caption(f"Last snapshot: {latest_time.strftime('%I:%M %p ET').lstrip('0')}")
        chart=current.pivot_table(index="recorded_at",columns="house",values="wait_minutes",aggfunc="mean").sort_index()
        st.subheader("Wait times throughout the night")
        st.line_chart(chart)

st.divider()
st.subheader("Historical HHN nights")
if not df.empty:
    dates=sorted([d for d in df["event_date"].dropna().unique() if operating(d)],reverse=True)
    if dates:
        selected=st.selectbox("Select an HHN night",dates,format_func=lambda d:d.strftime("%A, %B %-d, %Y"))
        chosen=df[df["event_date"]==selected]
        summary=chosen.groupby("house")["wait_minutes"].agg(["mean","min","max"]).round(1)
        summary.columns=["Average","Minimum","Maximum"]
        st.dataframe(summary.sort_values("Average",ascending=False),use_container_width=True)
        chart=chosen.pivot_table(index="recorded_at",columns="house",values="wait_minutes",aggfunc="mean").sort_index()
        st.line_chart(chart)
    st.subheader("All collected data")
    st.download_button("Download CSV",df.to_csv(index=False).encode(), "hhn35_wait_times.csv","text/csv")
    st.download_button("Download Excel",excel_bytes(df),"hhn35_wait_times.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

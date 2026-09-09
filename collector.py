import csv
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

TZ = ZoneInfo("America/New_York")
DATA_FILE = Path("data/waits.csv")
API_URL = "https://queue-times.com/parks/65/queue_times.json"
LIVE_URL = "https://queue-times.com/en-US/parks/65/queue_times"

HOUSES = ["Cybergoria","Evil Dead Burn","H.R. Bloodengutz","Hellraiser","INVASION",
          "Jack & Oddfellow","MADLANDS","Ozzy Osbourne","Sinners","Stranger Things 5"]
HEADER = ["recorded_at","event_date","house","wait_minutes","status"]

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").replace("’","'").replace("‘","'")).strip().lower()

def event_date_for(dt):
    return (dt - timedelta(days=1)).date() if dt.hour < 6 else dt.date()

def operating(d):
    return d.weekday() not in (0, 1)  # Monday/Tuesday closed

def api_rides(data):
    rides=[]
    for land in data.get("lands", []):
        rides.extend(land.get("rides",[]) or [])
    rides.extend(data.get("rides",[]) or [])
    seen=set(); result=[]
    for r in rides:
        key=(r.get("id"),r.get("name"))
        if key not in seen:
            seen.add(key); result.append(r)
    return result

def from_api():
    data=requests.get(API_URL,timeout=30).json()
    rides=api_rides(data); found={}
    for target in HOUSES:
        matches=[r for r in rides if norm(target) in norm(r.get("name",""))]
        if matches:
            r=matches[0]
            found[target]=(int(r.get("wait_time") or 0),"open" if r.get("is_open") else "closed")
    print(f"API returned {len(rides)} rides; matched {len(found)}/{len(HOUSES)} houses.")
    return found

def from_live_page():
    r=requests.get(LIVE_URL,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
    text=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
    found={}
    for target in HOUSES:
        i=norm(text).find(norm(target))
        if i>=0:
            m=re.search(r"(\d+)\s*(?:min|mins|minute|minutes)\b",text[i:i+500],re.I)
            if m: found[target]=(int(m.group(1)),"open")
    print(f"Live-page fallback matched {len(found)}/{len(HOUSES)} houses.")
    return found

def migrate_and_clean(rows):
    kept=[]
    for row in rows:
        try:
            ed=row.get("event_date","").strip()
            if not ed:
                ed=event_date_for(datetime.fromisoformat(row["recorded_at"])).isoformat()
            if operating(datetime.fromisoformat(ed).date()):
                kept.append({"recorded_at":row.get("recorded_at",""),"event_date":ed,
                              "house":row.get("house",""),"wait_minutes":row.get("wait_minutes",""),
                              "status":row.get("status","")})
        except Exception:
            pass
    return kept

def main():
    DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
    now=datetime.now(TZ); event_date=event_date_for(now)

    existing=[]
    if DATA_FILE.exists() and DATA_FILE.stat().st_size:
        with DATA_FILE.open(newline="",encoding="utf-8") as f:
            existing=list(csv.DictReader(f))
    existing=migrate_and_clean(existing)

    if not operating(event_date):
        with DATA_FILE.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=HEADER); w.writeheader(); w.writerows(existing)
        print(f"HHN is closed for event date {event_date}. Cleaned non-operating-day records; no collection performed.")
        return

    try: found=from_api()
    except Exception as e:
        print(f"API failed: {e}"); found={}
    if len(found)<len(HOUSES):
        try:
            for h,v in from_live_page().items(): found.setdefault(h,v)
        except Exception as e: print(f"Live-page fallback failed: {e}")

    new=[]
    for h in HOUSES:
        if h in found:
            wait,status=found[h]
            new.append({"recorded_at":now.isoformat(),"event_date":event_date.isoformat(),
                         "house":h,"wait_minutes":wait,"status":status})
    with DATA_FILE.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=HEADER); w.writeheader(); w.writerows(existing+new)
    print(f"Recorded {len(new)}/{len(HOUSES)} houses for HHN night {event_date}.")

if __name__=="__main__":
    main()

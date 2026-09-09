import csv
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

API_URL = "https://queue-times.com/parks/65/queue_times.json"
LIVE_PAGE_URL = "https://queue-times.com/en-US/parks/65/queue_times"
DATA_FILE = Path("data/waits.csv")
TZ = ZoneInfo("America/New_York")

HOUSES = [
    "Cybergoria", "Evil Dead Burn", "H.R. Bloodengutz", "Hellraiser",
    "INVASION", "Jack & Oddfellow", "MADLANDS", "Ozzy Osbourne",
    "Sinners", "Stranger Things 5"
]

HEADERS = {
    "User-Agent": "HHN-35-Wait-Tracker/1.0"
}

def norm(s):
    return " ".join(str(s).lower().replace("’", "'").split())

def api_rides(payload):
    rides = []
    for land in payload.get("lands", []) or []:
        rides.extend(land.get("rides", []) or [])
    rides.extend(payload.get("rides", []) or [])
    return rides

def from_api():
    r = requests.get(API_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    payload = r.json()
    rides = api_rides(payload)
    found = {}
    for ride in rides:
        name = norm(ride.get("name", ""))
        for house in HOUSES:
            if house not in found and norm(house) in name:
                found[house] = {
                    "wait": int(ride.get("wait_time", 0) or 0),
                    "status": "Open" if ride.get("is_open") else "Closed",
                }
    return found, len(rides)

def from_live_page():
    r = requests.get(LIVE_PAGE_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    text = norm(" ".join(BeautifulSoup(r.text, "html.parser").stripped_strings))
    found = {}
    for house in HOUSES:
        pos = text.find(norm(house))
        if pos < 0:
            continue
        window = text[pos:pos + len(house) + 100]
        match = re.search(r"(\d+)\s+mins?", window)
        if match:
            found[house] = {"wait": int(match.group(1)), "status": "Open"}
        elif "closed" in window:
            found[house] = {"wait": "", "status": "Closed"}
    return found

def main():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    # HHN 35 does not operate on Mondays or Tuesdays.
    # Do not collect on those days, and remove any previously
    # recorded Monday/Tuesday rows so they cannot pollute the dashboard.
    now = datetime.now(TZ)
    if now.weekday() in (0, 1):  # Monday=0, Tuesday=1
        if DATA_FILE.exists() and DATA_FILE.stat().st_size > 0:
            rows = []
            with DATA_FILE.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        row_dt = datetime.fromisoformat(row["recorded_at"])
                        if row_dt.weekday() not in (0, 1):
                            rows.append(row)
                    except Exception:
                        continue

            header = ["recorded_at", "house", "wait_minutes", "status"]
            with DATA_FILE.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)

            print(f"HHN is closed on Monday/Tuesday. Removed non-operating-day records; kept {len(rows)} rows.")
        else:
            print("HHN is closed on Monday/Tuesday. No collection performed.")
        return

    found = {}

    try:
        found, ride_count = from_api()
        print(f"API returned {ride_count} rides; matched {len(found)}/10 houses.")
    except Exception as e:
        print("API error:", e)

    if len(found) < len(HOUSES):
        try:
            page = from_live_page()
            for house, value in page.items():
                found.setdefault(house, value)
            print(f"Live-page fallback matched {len(page)}/10 houses.")
        except Exception as e:
            print("Live-page fallback error:", e)

    timestamp = datetime.now(TZ).isoformat(timespec="seconds")
    new_rows = []
    for house in HOUSES:
        if house in found:
            v = found[house]
            new_rows.append([timestamp, house, v["wait"], v["status"]])
        else:
            new_rows.append([timestamp, house, "", "Not found"])

    header = ["recorded_at", "house", "wait_minutes", "status"]
    exists = DATA_FILE.exists() and DATA_FILE.stat().st_size > 0

    with DATA_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerows(new_rows)

    print(f"Recorded {len(found)}/10 houses at {timestamp}.")

if __name__ == "__main__":
    main()

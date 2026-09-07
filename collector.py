import csv
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

HEADERS = {
    "User-Agent": "HHN-35-Wait-Tracker/1.0"
}


def norm(s):
    return " ".join(
        str(s)
        .lower()
        .replace("’", "'")
        .split()
    )


def api_rides(payload):
    rides = []

    for land in payload.get("lands", []) or []:
        rides.extend(land.get("rides", []) or [])

    rides.extend(payload.get("rides", []) or [])

    return rides


def from_api():
    """
    Get wait times from Queue-Times API.

    Important:
    is_open=False does NOT automatically mean permanently closed.
    We initially mark it as unavailable and let the live-page
    check determine whether it is Delayed or Closed.
    """

    r = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=20
    )

    r.raise_for_status()

    payload = r.json()

    rides = api_rides(payload)

    found = {}

    for ride in rides:

        name = norm(
            ride.get("name", "")
        )

        for house in HOUSES:

            if (
                house not in found
                and norm(house) in name
            ):

                is_open = ride.get(
                    "is_open",
                    False
                )

                wait_time = ride.get(
                    "wait_time",
                    0
                )

                if is_open:

                    found[house] = {
                        "wait": int(
                            wait_time or 0
                        ),
                        "status": "Open",
                    }

                else:

                    found[house] = {
                        "wait": 0,
                        "status": "Unavailable",
                    }

    return found, len(rides)


def extract_house_status(text, house):
    """
    Look around the house name on the live page.

    Possible results:
      - Open + wait time
      - Delayed
      - Closed
      - Unknown
    """

    normalized_text = norm(text)
    normalized_house = norm(house)

    pos = normalized_text.find(
        normalized_house
    )

    if pos < 0:
        return None

    # Look farther than the old 100-character window.
    window = normalized_text[
        pos:pos + len(normalized_house) + 250
    ]

    # Check for a numeric wait first.
    match = re.search(
        r"(\d+)\s+mins?",
        window
    )

    if match:

        return {
            "wait": int(match.group(1)),
            "status": "Open",
        }

    # Delayed / temporarily unavailable.
    if re.search(
        r"\bdelayed\b",
        window,
        re.IGNORECASE
    ):

        return {
            "wait": 0,
            "status": "Delayed",
        }

    # Closed.
    if re.search(
        r"\bclosed\b",
        window,
        re.IGNORECASE
    ):

        return {
            "wait": 0,
            "status": "Closed",
        }

    return None


def from_live_page():

    r = requests.get(
        LIVE_PAGE_URL,
        headers=HEADERS,
        timeout=20
    )

    r.raise_for_status()

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    text = " ".join(
        soup.stripped_strings
    )

    found = {}

    for house in HOUSES:

        result = extract_house_status(
            text,
            house
        )

        if result is not None:
            found[house] = result

    return found


def main():

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    found = {}

    # -----------------------------------------------------
    # STEP 1: Get API data
    # -----------------------------------------------------

    try:

        found, ride_count = from_api()

        print(
            f"API returned {ride_count} rides; "
            f"matched {len(found)}/10 houses."
        )

    except Exception as e:

        print(
            "API error:",
            e
        )


    # -----------------------------------------------------
    # STEP 2: Check the live page
    #
    # The live page gets priority because it can tell us
    # whether an unavailable house is actually Delayed
    # or Closed.
    # -----------------------------------------------------

    try:

        page = from_live_page()

        print(
            f"Live-page check matched "
            f"{len(page)}/10 houses."
        )

        for house, value in page.items():

            # Live-page result overrides API result.
            found[house] = value

    except Exception as e:

        print(
            "Live-page error:",
            e
        )


    # -----------------------------------------------------
    # STEP 3: Write timestamped records
    # -----------------------------------------------------

    timestamp = datetime.now(
        TZ
    ).isoformat(
        timespec="seconds"
    )

    new_rows = []

    for house in HOUSES:

        if house in found:

            value = found[house]

            new_rows.append(
                [
                    timestamp,
                    house,
                    value["wait"],
                    value["status"],
                ]
            )

        else:

            new_rows.append(
                [
                    timestamp,
                    house,
                    "",
                    "Not found",
                ]
            )


    # -----------------------------------------------------
    # STEP 4: Append to waits.csv
    # -----------------------------------------------------

    header = [
        "recorded_at",
        "house",
        "wait_minutes",
        "status",
    ]

    exists = (
        DATA_FILE.exists()
        and DATA_FILE.stat().st_size > 0
    )

    with DATA_FILE.open(
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        if not exists:
            writer.writerow(header)

        writer.writerows(new_rows)


    print(
        f"Recorded {len(found)}/10 houses "
        f"at {timestamp}."
    )


if __name__ == "__main__":
    main()

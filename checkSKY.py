#!/usr/bin/env python3

##############################################################################80
# Astroligical Phenomena Notice 20231227
##############################################################################80
# Description: Sends notifications of astrological phenomena to allow users to
# have something to blame a bad day on.
# Usage via CRON: (Runs every day at 0706)
#   6 7 * * * cd /path/to/folder && ./checkSKY.py --cron 2>&1 | ./tailog.py
# Usage via CLI:
#   cd /path/to/folder && ./checkSKY.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import os, re, sys
import ephem

from requests import get
import time
from datetime import datetime, timedelta
from utils import cPrint, getBaseParser, sendNotification

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Checks for astrological phenomena.")
args = parser.parse_args()

##############################################################################80
# Check if today is a supermoon
##############################################################################80
def checkMoonDistance():
    cPrint("Checking moon position...", "BLUE") if args.debug else None
    moon = ephem.Moon()
    today = datetime.now()

    moon.compute(today)
    distance = moon.earth_distance * ephem.meters_per_au / 1000  # distance in kilometers

    # Criteria for supermoon and micromoon
    isSupermoon = moon.phase >= 98 and distance < 360000
    isMicromoon = moon.phase >= 98 and distance > 405000

    if isSupermoon:
        return True, "Today is a Supermoon."
    elif isMicromoon:
        return True, "Today is a Micromoon."
    else:
        return False, "Nothing special about today's moon."

##############################################################################80
# Check if Mercury is in retrograde
##############################################################################80
def isMercuryInRetrograde():
    cPrint("Looking for Mercury...", "BLUE") if args.debug else None
    
    today = datetime.now().strftime("%Y-%m-%d")
    response = get(f"https://mercuryretrogradeapi.com?date={today}")
    retrograde = response.status_code == 200 and response.json().get("is_retrograde", False)
    if retrograde:
        return True, "Mercury is in retrograde today!"
    else:
        return False, "Mercury isn't in retrograde today."

##############################################################################80
# Check if the moon was full last night
##############################################################################80
def getMoonPhase():
    cPrint("Checking the moon's phase...", "BLUE") if args.debug else None
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # USNO API base URL for Earth's seasons
    base_url = "https://aa.usno.navy.mil/api/moon/phases/date"

    # Query parameters
    params = {"date": yesterday, "ID":"hlsiira"}

    try:
        response = get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                phase = data["phasedata"][0]["phase"]  # Accessing the 'Phase' attribute
                if phase == "Full Moon":
                    return True, "The moon was full last night."
                else:
                    return False, f"The moon was a {phase} last night."
            else:
                return False, "No moon phase data available."
        else:
            return False, "Failed to retrieve moon phase data."
    except Exception as e:
        return False, f"Error while retrieving moon phase: {e}"    

##############################################################################80
# Check if today is solstice or equinox
##############################################################################80
def checkSeasonStart():
    cPrint("Determining if today is special...", "BLUE") if args.debug else None
    
    # Get the current year and today's date
    day = datetime.now().day
    month = datetime.now().month
    year = datetime.now().year

    # USNO API base URL for Earth's seasons
    base_url = "https://aa.usno.navy.mil/api/seasons"

    # Query parameters
    params = {"year": year, "ID":"hlsiira"}

    try:
        response = get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()["data"]
            # Check each season's date
            for item in data:
                if item["day"] == day and item["month"] == month:
                    return True, f"Today is the {item['phenom']}!"
            return False, "Nothing special about today."
        else:
            return False, "Failed to retrieve seasonal data."
    except Exception as e:
        return False, f"Error while retrieving seasonal data: {e}"  

##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint("Beginning main execution...", "BLUE") if args.debug else None

    metrics = [isMercuryInRetrograde(), getMoonPhase(), checkSeasonStart(), checkMoonDistance()]

    message = "<b>Phenomena:</b>"
    sendNotice = False

    for notice,state in metrics:
        if notice:
            sendNotice = True
        message += f"\n\t- {state}"
        
    if sendNotice or args.test:
        cPrint("Astrological events detected, sending notification...", "RED")
        subject = "Astrological phenomena detected"

        sendNotification(subject, message)            
    else:
        cPrint("No astrological events.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)    

if __name__ == "__main__":
    main()

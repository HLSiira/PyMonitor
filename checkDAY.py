#!/usr/bin/env python3

##############################################################################80
# Important Date Notifier 20240102
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
from datetime import datetime, timedelta
import csv
from utils import cPrint, getBaseParser, sendNotification, CONF

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Checks for astrological phenomena.")
args = parser.parse_args()

##############################################################################80
# Configurations
##############################################################################80
storagePath = CONF["keyDates"]["storagePath"]
threshold = CONF["keyDates"]["threshold"]


##############################################################################80
# Check if today is a supermoon
##############################################################################80
def calculateAge(anniversary, today):
    age = today.year - anniversary.year - ((today.month, today.day) < (anniversary.month, anniversary.day))
    return age

##############################################################################80
# Check if today is a supermoon
##############################################################################80
def checkDate():
    cPrint(f"Comparing dates...", "BLUE") if args.debug else None
    today = datetime.now()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    # futureDates = getFutureDates()
    
    events = {}

    with open(storagePath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            event = datetime.strptime(row["Event Value"], "%Y-%m-%d")
            anniversary = event.replace(year=today.year)
            if 0 <= (anniversary - today).days < threshold:  # Check if the event is within the next 7 days
                structuredEvent = {
                    "name": f"{row['Given Name']} {row['Family Name']}",
                    "type": row["Event Type"],
                    "year": event.year,
                    "age": today.year - event.year,
                    "isToday": (anniversary == today)
                }
                anniversary = anniversary.strftime("%b %d")
                if anniversary not in events:
                	events[anniversary] = [structuredEvent]
                else:
                	events[anniversary].append(structuredEvent)
                	
                
    # Sort the events by date
    events = dict(sorted(events.items()))
    return events

def main():
    cPrint("Beginning main execution...", "BLUE") if args.debug else None

    events = checkDate()

    if any(events) or args.test:
        cPrint("Key events today, sending notification...", "RED")
        subject = "Notable event(s) coming:"
        message = ""
        for date in events.keys():
        	newline = "\n" if message != "" else ""
        	if events[date][0]["isToday"]:
        		message += f"{newline}<b><font color='#0074D9'>- {date} (today):</font></b>"
        	else:
        		message += f"{newline}<b>- {date}:</b>"
        	for event in events[date]:
	            if event["type"] == "annual appointment":
	                message += f"\n\t- <b><font color='#ff4d3e'>{event['type']}: {event['name']}</font><\b>"
	            else:
	                message += f"\n\t- {event['type']}: {event['name']} ({event['year']}/{event['age']}y)"

        sendNotification(subject, message)            
    else:
        cPrint("No key dates.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)    

if __name__ == "__main__":
    main()

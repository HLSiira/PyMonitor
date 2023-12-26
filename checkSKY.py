#!/usr/bin/env python3

import os, sys
import re
import ephem

from requests import get
import requests
from datetime import datetime, timedelta
from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")


def check_today_supermoon_micromoon():
    moon = ephem.Moon()
    today = datetime.now()

    moon.compute(today)
    distance_km = moon.earth_distance * ephem.meters_per_au / 1000  # distance in kilometers

    # Criteria for supermoon and micromoon
    is_supermoon = moon.phase >= 98 and distance_km < 360000
    is_micromoon = moon.phase >= 98 and distance_km > 405000

    if is_supermoon:
        return "Today is a Supermoon."
    elif is_micromoon:
        return "Today is a Micromoon."
    else:
        return False

# Function to check if Mercury is in retrograde
def is_mercury_in_retrograde():
    today = datetime.now().strftime('%Y-%m-%d')
    response = get(f"https://mercuryretrogradeapi.com?date={today}")
    if response.status_code == 200:
        return response.json().get('is_retrograde', False)
    return False

# Function to check if the moon was full last night
def was_moon_full_last_night():
    yesterday = (datetime.now() - timedelta(1)).strftime('%Y-%m-%d')
    response = get(f"https://moon-phase.p.rapidapi.com/basic?date={yesterday}")
    if response.status_code == 200:
        moon_data = response.json()
        return moon_data.get('phase_name') == 'Full Moon'
    return False
    
def check_today_solstice_equinox():
    # Get the current year and today's date
    current_year = datetime.now().year
    today = datetime.now().date()

    # USNO API base URL for Earth's seasons
    base_url = "https://aa.usno.navy.mil/api/earth/seasons"

    # Query parameters
    params = {"year": current_year}

    # Sending a GET request to the USNO API
    response = get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        # Check each season's date
        for season, date_str in data.items():
            season_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").date()
            if today == season_date:
                return f"Today is the {season}."
        return False
    else:
        return False



# Function to get special astronomical events (implement based on the Astronomy API)
def get_special_astronomical_events():
    # Implementation depends on the specifics of the API and the types of events you want to include
    pass

messages = []
if is_mercury_in_retrograde():
    messages.append("Mercury is in retrograde today!")
if was_moon_full_last_night():
    messages.append("The moon was full last night.")
    
moon = check_today_supermoon_micromoon()
if moon: messages.append(moon)

seasonalToday = check_today_solstice_equinox()
if seasonalToday: messages.append(seasonalToday)

# Add more events based on the Astronomy API
special_events = get_special_astronomical_events()
if special_events:
    messages.extend(special_events)

if messages:
    cPrint(f"Events detected, sending notification...")
    if DEBUG:
        print("\n".join(messages))
    else:
        send("Astronomical Event", "\n".join(messages))
elif DEBUG:
    cPrint(f"No astrological events.")

exit(0)

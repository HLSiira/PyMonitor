#!/usr/bin/env python3

# Use to inline: https://www.campaignmonitor.com/resources/tools/css-inliner/
# Use to test emails: https://app.postdrop.io/
# Use to check email: https://www.htmlemailcheck.com/check/

import os, sys
import socket
import requests
import json

from datetime import datetime

# from premailer import transform
host = socket.gethostname().title()
name = os.path.basename(sys.argv[0])

# SCANID is also the date/time
SCANID = datetime.now().strftime("%Y%m%d%H%M")

def cPrint(msg):
    print(f"{name}: {SCANID} {msg}")

def hasFlag(flg):
    return len(sys.argv) > 1 and flg in sys.argv[1]

def formatIP(ip):
    octets = ip.split('.')
    # Pad each octet with zeros to make it three digits long
    # octets[3] = octets[3].zfill(3)
    octets = [octet.zfill(3) for octet in octets]
    # Join the octets back into a formatted IP address
    return ".".join(octets)

def loadCredentials(filename="data/config.json"):
    with open(filename, "r") as f:
        data = json.load(f)
    return data["user_key"], data["api_token"]

def send(subject, message):
    user_key, api_token = loadCredentials()

    data = {
        'token': api_token,
        'user': user_key,
        'message': message,
        'title': f"{host}: {subject}",
        'html' : 1,
        # 'monospace': 1,
        'url': None,
        'url_title': None,
        'priority': 0,
        'ttl': 43200
    }

    response = requests.post('https://api.pushover.net/1/messages.json', data=data)
    return response.text  # Returns the API's response which can be useful for debugging or confirmation

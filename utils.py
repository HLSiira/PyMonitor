#!/usr/bin/env python3

##############################################################################80
# Utils 20231224
# Description
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import os, sys
import socket
import requests
import json
import argparse

from datetime import datetime

##############################################################################80
# Global variables
##############################################################################80
SCRIPTNAME = "defaultScript"
HOSTNAME = "defaultHOST"
SCANID = "defaultScanID"
args = False

def initGlobals():
    global HOSTNAME, SCRIPTNAME, SCANID
    HOSTNAME = socket.gethostname().title()
    SCRIPTNAME = os.path.basename(sys.argv[0])
    SCANID = datetime.now().strftime("%Y%m%d%H%M")
    
def getBaseParser(description="Default description"):
    global args
    parser = argparse.ArgumentParser(description=description)
    # Add common arguments here
    parser.add_argument("-d", "--debug", action="store_true", help="Activate debug messages.")
    parser.add_argument("-c", "--cron", action="store_true", help="Indicates script is running as cron.")
    parser.add_argument("-t", "--test", action="store_true", help="Forces test, ignores cached files.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Disable sending notifcations.")
    return parser

##############################################################################80
# Print helper to add color: Red(0), Blue(1), Green(2), and Reset(3)
##############################################################################80
COLORS = {
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "BLUE": "\033[94m",
    "RESET": "\033[0m"
}
def cPrint(message, color="RESET"):
    color = COLORS[color]
    if len(sys.argv) > 1 and "c" in sys.argv[1]:
        print(f"{SCRIPTNAME}: {SCANID} {message}")
    else:
        print(f"{color}{message}" + COLORS["RESET"])

##############################################################################80
# Parse flags from CLI
##############################################################################80
def hasFlag(flg):
    return len(sys.argv) > 1 and flg in sys.argv[1]
    
##############################################################################80
# Check if sudo, some scripts require it
##############################################################################80
def checkSudo():
    if os.geteuid() != 0:
        cPrint("Script requires root privileges; please run it with sudo.", "RED")
        sys.exit(1)    

##############################################################################80
# Format IP Addresses to common length, better visual formatting
##############################################################################80
def formatIP(ip):
    octets = ip.split(".")
    octets = [octet.zfill(3) for octet in octets]
    return ".".join(octets)

##############################################################################80
# Load credentials from json file
##############################################################################80
def loadCredentials(filename="data/config.json"):
    with open(filename, "r") as f:
        data = json.load(f)
    return data["userKey"], data["apiToken"]

##############################################################################80
# Using Pushover credentials, send a notification
##############################################################################80
def sendNotification(subject, message, priority=0):
    if args and args.quiet:
        return True

    userKey, apiToken = loadCredentials()

    data = {
        "token": apiToken,
        "user": userKey,
        "message": message,
        "title": f"{HOSTNAME}: {subject}",
        "html" : 1,
        "priority": priority,
        "ttl": 43200
    }

    response = requests.post("https://api.pushover.net/1/messages.json", data=data)
    return response.text  # Returns the API's response which can be useful for debugging or confirmation

# Initialization Code
if 'utils' in sys.modules:
    # Initialize only if this module is being imported
    initGlobals()
    # config = load_configuration()
    # Set other global configurations based on 'config'
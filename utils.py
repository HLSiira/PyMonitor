#!/usr/bin/env python3

##############################################################################80
# Utility Helper Functions 20231227
##############################################################################80
# Description: Check ISP speeds and maintains human-readable records, sends
# notifications via PushOver if speeds are outside of defined bounderies.
# Usage: imports only
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
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
CONF = {}
args = False


def initGlobals():
    global HOSTNAME, SCRIPTNAME, SCANID, CONF
    HOSTNAME = socket.gethostname().title()
    SCRIPTNAME = os.path.basename(sys.argv[0])
    SCRIPTNAME = os.path.splitext(SCRIPTNAME)[0]

    SCANID = datetime.now().strftime("%Y%m%d%H%M")
    CONF = loadConfig()


def getBaseParser(description="Default description"):
    global args
    parser = argparse.ArgumentParser(description=description)
    # Add common arguments here
    parser.add_argument(
        "-c",
        "--cron",
        action="store_true",
        help="Formats messages into loggable format, with more information.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Activates debug messages during run, to track progress.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Disables push notifications, prints message to terminal.",
    )
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Overrides passing conditions to test notifications.",
    )
    return parser


##############################################################################80
# Print helper to add color: Red(0), Blue(1), Green(2), and Reset(3)
##############################################################################80
COLORS = {
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "BLUE": "\033[94m",
    "RESET": "\033[0m",
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
def loadConfig(filename="data/config.json"):
    with open(filename, "r") as f:
        data = json.load(f)
    return data


##############################################################################80
# Using Pushover credentials, send a notification
##############################################################################80
def pingHealth(uuid=False):
    # Ensure the 'healthChecks' key is present in the CONF dictionary
    healthChecks = CONF.get("healthChecks")

    # Check if the subkey 'SCRIPTNAME' is present
    if not uuid and healthChecks and SCRIPTNAME in healthChecks:
        uuid = healthChecks[SCRIPTNAME]

    if not uuid:
        return

    response = requests.post(f"https://hc-ping.com/{uuid}")
    return response.status_code


##############################################################################80
# Using Pushover credentials, send a notification
##############################################################################80
def sendNotification(subject, message, priority=0):
    if len(sys.argv) > 1 and "q" in sys.argv[1]:
        cPrint(subject)
        cPrint(message)
        return False

    userKey = CONF["userKey"]
    apiToken = CONF["apiToken"]

    data = {
        "token": apiToken,
        "user": userKey,
        "message": message,
        "title": f"{HOSTNAME}: {subject}",
        "html": 1,
        "priority": priority,
        "ttl": CONF["expiration"],
    }

    response = requests.post("https://api.pushover.net/1/messages.json", data=data)
    return (
        response.text
    )  # Returns the API's response which can be useful for debugging or confirmation


# Initialization Code
if "utils" in sys.modules:
    # Initialize only if this module is being imported
    initGlobals()
    # config = load_configuration()
    # Set other global configurations based on 'config'

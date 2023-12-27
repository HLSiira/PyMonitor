#!/usr/bin/env python3

##############################################################################80
# IPv4 Check 20231224
##############################################################################80
# Pulls IP Address from my domain and sends a notification if it's different
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/docs/LICENSE.md for more.
##############################################################################80

import sys, re, requests
from utils import getBaseParser, cPrint, sendNotification, formatIP

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Sends notification if IPv4 address has changed.")
args = parser.parse_args()

##############################################################################80
# Get public IP from website
##############################################################################80
def getPublicIP():
    cPrint(f"Pulling Public IP...", "BLUE") if args.debug else None
    try:
        response = requests.get("https://siira.io/ip")
        response.raise_for_status()
        publicIP = response.text
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", publicIP):
            return publicIP
        else:
            cPrint("API Error/Invalid IP Response", "RED")
            sys.exit(1)
    except requests.RequestException as e:
        cPrint(f"Error fetching IP: {e}", "RED")
        sys.exit(1)

##############################################################################80
# Read old IP from file
##############################################################################80
def readOldIP(path="data/ipaddress"):
    cPrint(f"Reading old IP...", "BLUE") if args.debug else None
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return False

##############################################################################80
# Save new IP to file
##############################################################################80
def saveNewIP(ip,path="data/ipaddress"):
    cPrint(f"Saving new IP...", "BLUE") if args.debug else None
    with open(path, "w") as f:
        f.write(ip)

##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None
    newIP = formatIP(getPublicIP())
    oldIP = readOldIP()

    if newIP != oldIP or args.test:
        saveNewIP(newIP)

        cPrint(f"IP change({newIP}), sending notification...", "GREEN")
        subject = "IP address changed"
        message = f"IP Address has changed from {oldIP} to {newIP}"

        if args.debug:
            cPrint(subject)
            cPrint(message)
        else:
            sendNotification(subject, message)            
    else:
        cPrint(f"No change, public IP address is {newIP}.")
    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)    

if __name__ == "__main__":
    main()
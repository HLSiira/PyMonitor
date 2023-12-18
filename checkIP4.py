#!/usr/bin/env python3

import os, sys
import re

from requests import get
from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")

newIP = get("https://siira.io/ip").text

if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", newIP):
    cPrint("API Error/Invalid IP Response")
    exit(1)

oldIP = ""

try:
    f = open("data/ipaddress", "r")
    oldIP = f.read()
    f.close()
except:
    pass

if newIP != oldIP:
    cPrint(f"IP Change, Emailing new IP({newIP})...")

    f = open("data/ipaddress", "w")
    f.write(newIP)

    update = {
        "key1": "Old IP Address",
        "key2": "New IP Address",
        "val1": oldIP,
        "val2": newIP,
    }

    if DEBUG:
        print(update)
    else:
        send("IP Change", f"IP Address has changed from {oldIP} to {newIP}")

else:
    cPrint(f"No change, public IP address is {newIP}")

exit(0)

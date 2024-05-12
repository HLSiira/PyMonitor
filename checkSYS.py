#!/usr/bin/env python3

##############################################################################80
# System Health Check 20231224
##############################################################################80
# Description: Checks system information and sends notification if outside
# predefined bounderies.
# USAGE via CRON: (Runs every 15 minutes)
#   */15 * * * * cd /path/to/folder && ./checkSYS.py 2>&1 | ./tailog.py
# USAGE via CLI:
#   cd /path/to/folder && ./checkSYS.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/docs/LICENSE.md for more.
##############################################################################80

import os, re, sys
import math
import psutil
from utils import cPrint, getBaseParser, sendNotification, CONF

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Scans SSH Auth log and signals last 7 days of activity.")
args = parser.parse_args()


##############################################################################80
# Helper: Convert to display human readable sizes
##############################################################################80
def bytesToHuman(bytes):
    if bytes == 0:
        return "0B"
    sizes = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p)
    return s, sizes[i]


##############################################################################80
# Check CPU usage
##############################################################################80
def checkCPU(threshold=85):
    cPrint(f"Checking CPU...", "BLUE") if args.debug else None
    percentage = psutil.cpu_percent(interval=1)
    return percentage > threshold, f"CPU usage: {percentage}%"


##############################################################################80
# Checks system memory usage.
##############################################################################80
def checkMemory(threshold=75):
    cPrint(f"Checking Memory...", "BLUE") if args.debug else None
    memory = psutil.virtual_memory()
    percentage = memory.used / memory.total * 100
    used, cat = bytesToHuman(memory.used)
    total, cat = bytesToHuman(memory.total)
    state = f"Memory: {used}/{total}{cat} ({percentage:.0f}%)"
    return percentage > threshold, state


##############################################################################80
# Check storage disk usage
##############################################################################80
def checkStorage(threshold=80):
    cPrint(f"Checking Storage...", "BLUE") if args.debug else None
    storage = psutil.disk_usage("/")
    percentage = storage.used / storage.total * 100
    used, cat = bytesToHuman(storage.used)
    total, cat = bytesToHuman(storage.total)
    state = f"Storage: {used}/{total}{cat} ({percentage:.0f}%)"
    return percentage > threshold, state


##############################################################################80
# Begin main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None

    cpuThreshold = CONF["systemHealth"]["CPU"]
    memoryThreshold = CONF["systemHealth"]["memory"]
    storageThreshold = CONF["systemHealth"]["storage"]

    metrics = [
        checkCPU(cpuThreshold),
        checkMemory(memoryThreshold),
        checkStorage(storageThreshold),
    ]

    message = "<b>System Metrics:</b>"
    sendNotice = False

    for warning, state in metrics:
        if warning:
            sendNotice = True
        message += f"\n\t- {state}"

    if sendNotice or args.test:
        cPrint(f"System alert, sending notification...", "RED")
        subject = "System health alert"

        sendNotification(subject, message)
    else:
        cPrint("All systems nominal.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)


if __name__ == "__main__":
    main()

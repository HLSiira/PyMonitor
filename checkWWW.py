#!/usr/bin/env python3

##############################################################################80
# Apt Update Notifications 20231227
##############################################################################80
# Description: Check for package updates in a Debian-based system, categorizing
# them into regular and security updates, sends notifications via PushOver
# Usage via CRON: (Runs every day at 0701)
#   1 7 * * * cd /path/to/folder && ./checkAPT.py --cron 2>&1 | ./tailog.py
# Usage via CLI:
#   cd /path/to/folder && ./checkAPT.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import os, sys, subprocess
import apt, apt_pkg
import re
import logging

from datetime import datetime
from utils import COLORS, cPrint, getBaseParser, pingHealth, sendNotification

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Sends notifications when package updates are available.")
args = parser.parse_args()

# Path to your Apache error log file
logFilePath = "/var/log/apache2/error.log"
pattern = re.compile(r"\[(.*?)\] \[(.*?):(.*?)\] \[pid .*?\] \[client (.*?):.*?\] (.*)")


##############################################################################80
# Function to format datetime to YYYYMMDD
##############################################################################80
def formatDatetime(datetime_str):
    dt = datetime.strptime(datetime_str, "%a %b %d %H:%M:%S.%f %Y")
    return dt.strftime("%Y%m%d %H:%M")


##############################################################################80
# Function to add color based on severity
##############################################################################80
def color_severity(severity):
    colorMap = {
        "notice": "BLUE",  # Blue
        "info": "GREEN",  # Green
        "warn": "YELLOW",  # Yellow
        "error": "RED",  # Red
    }
    return colorMap.get(severity, "RESET")


##############################################################################80
# Parse Apache Log
##############################################################################80
def parseApacheLog(logFilePath):
    with open(logFilePath, "r") as file:
        lines = file.readlines()

    errors = []

    for line in reversed(lines):
        match = pattern.match(line)
        if match:
            datetime_str = match.group(1)
            category = match.group(2)
            severity = match.group(3)
            ip = match.group(4)
            message = match.group(5)

            formatted_date = formatDatetime(datetime_str)
            severity_color = color_severity(severity)
            severity = COLORS[severity_color] + severity + COLORS["RESET"]
            log_lines = message.split("\\n")

            for log_line in log_lines:
                error_info = {
                    "Date": formatted_date,
                    "IP": ip,
                    "Log": log_line.strip(),
                    "Severity": severity,
                    "Referer": "N/A",  # Adjust if you need to extract the referer
                }
                errors.append(error_info)

        if len(errors) >= 10:
            break

    print(f"{'Date':<16} {'Severity':<10} {'Log':<50}")
    print("=" * 95)
    for error in errors:
        print(f"{error['Date']:<16} {error['Severity']:<10} {error['Log']:<50}")


##############################################################################80
# Main execution
##############################################################################80
def main():
    cPrint("Beginning main execution...", "BLUE") if args.debug else None
    parseApacheLog(logFilePath)
    exit()

    subject, message = "", ""

    if any(comPacks) or args.test:
        cPrint("Apache errors found, sending notification....", "BLUE")
        subject = f"{len(comPacks)}/{secCount} Updatable Package(s)"
        message = "<b>Packages:</b>"

        for pack in comPacks:
            url = create_package_url(pack["name"])
            name = f"{pack['name'][:21]}..." if len(pack["name"]) > 24 else pack["name"]
            if pack["security"]:
                message += f"\n\t- <font color='#ff4d3e'>{name}</font>"
            else:
                message += f"\n\t- {name}"

        sendNotification(subject, message)
    else:
        cPrint("No package updates.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

##############################################################################80
# SSH Weekly Activity Alert 20231226
# Description: Scans SSH Auth log and signals last 7 days of activity.
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import os, re, sys
from datetime import datetime, timedelta
from utils import checkSudo, cPrint, formatIP, getBaseParser, sendNotification

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Scans SSH Auth log and signals last 7 days of activity.")
args = parser.parse_args()

def parseLogins(logFile="/var/log/auth.log"):
    cPrint("Parsing SSH Logins...", "BLUE") if args.debug else None
    oneWeekAgo = datetime.now() - timedelta(days=7)
    entries = {}

    # Regex patterns to extract IP address and username
    ip_pattern = re.compile(r"from\s+(\d+\.\d+\.\d+\.\d+)")
    user_pattern = re.compile(r"for\s+(\w+)")

    with open(logFile, "r") as file:
        for line in file:
            if "Accepted" in line and "ssh" in line:
                parts = line.split()
                date_str = " ".join(parts[0:3])
                logDate = datetime.strptime(date_str, "%b %d %H:%M:%S")
                current_year = datetime.now().year
                logDate = logDate.replace(year=current_year)

                if logDate > oneWeekAgo:
                    logDate = logDate.strftime("%Y%m%d")
                    # Extract IP and username using regex
                    ip = ip_pattern.search(line)
                    user = user_pattern.search(line)
                    if ip and user:
                        ip = formatIP(ip.group(1))
                        user = user.group(1)
                        key = (logDate, ip, user)

                        if key in entries:
                            entries[key] += 1
                        else:
                            entries[key] = 1
    return entries    

##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint("Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()

    entries = parseLogins()

    if any(entries) or args.test:
        cPrint("SSH activity found, sending notification...", "GREEN")
        subject, message = "", ""
        subject = f"{len(entries)} SSH login(s) this week"
        message = "<b>SSH Connections:</b>"
        for (date, ip, user), count in entries.items():
            message += f"\n\t- {date}: {count} connections to <i>{user}</i> from {ip}"

        if args.debug:
            cPrint(subject)
            cPrint(message)
        else:
            sendNotification(subject, message)
    else:
        cPrint("No SSH activity found.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)   

if __name__ == "__main__":
    main()
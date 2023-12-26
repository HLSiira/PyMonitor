#!/usr/bin/env python3

from datetime import datetime, timedelta
import os, re
from utils import send, hasFlag, cPrint, SCANID, formatIP

DEBUG = hasFlag("d")
subject = "Weekly SSH Login Report"

def parseLogins(logFile="/var/log/auth.log"):
    oneWeekAgo = datetime.now() - timedelta(days=7)
    entries = {}

    # Regex patterns to extract IP address and username
    ip_pattern = re.compile(r'from\s+(\d+\.\d+\.\d+\.\d+)')
    user_pattern = re.compile(r'for\s+(\w+)')

    with open(logFile, 'r') as file:
        for line in file:
            if 'Accepted' in line and 'ssh' in line:
                parts = line.split()
                date_str = ' '.join(parts[0:3])
                logDate = datetime.strptime(date_str, '%b %d %H:%M:%S')
                current_year = datetime.now().year
                logDate = logDate.replace(year=current_year)

                if logDate > oneWeekAgo:
                    logDate = logDate.strftime('%Y%m%d')
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

entries = parseLogins()

if any(entries):
    messages = [f"\t- {date}: SSH to {user} from {ip} {count} times" for (date, ip, user), count in entries.items()]
    message = "\n".join(messages)
    cPrint(f"{subject}, sending notification...")
    
    if DEBUG:
        print(message)
    else:
        send(subject, message)

exit(0)

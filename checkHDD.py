#!/usr/bin/env python3

# source: https://uwot.eu/blog/projects/monitor-hard-disk-smart-status-python/

"""
A field study at Google covering over 100,000 consumer-grade drives from December 2005 to August 2006 found correlations between certain S.M.A.R.T. information and annualized failure rates:

In the 60 days following the first Offline_Uncorrectable (#198) detected as a result of an offline scan, the drive was, on average, 39 times more likely to fail than a similar drive for which no such error occurred.

First errors in Reallocations (#5 or #196) and Probational Counts (#197) were also strongly correlated to higher probabilities of failure.

Conversely, little correlation was found for increased temperature and no correlation for usage level. However, the research showed that a large proportion (56%) of the failed drives failed without recording any count in the "four strong S.M.A.R.T. warnings" identified as scan errors, reallocation count, offline reallocation and probational count.

Further, 36% of failed drives did so without recording any S.M.A.R.T. error at all, except the temperature, meaning that S.M.A.R.T. data alone was of limited usefulness in anticipating failures.

"""
import os, sys
import subprocess
import re

from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")
VERBOSE = hasFlag("v")

def querySMART(drive):
    p = subprocess.Popen(["/usr/sbin/smartctl", "-a", "/dev/" + drive], stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    output = output.decode("utf-8")

    if VERBOSE:
        print(output)

    health = {}
    alert = 0

    # Offline_Uncorrectable
    # Reallocated_Event_Count
    # Current_Pending_Sector
    crit = ["198", "196", "197"]

    # warn = ["", "", "", "", "", "", ""]

    # Wear_Leveling_Count
    # Reallocated_Sector_Ct
    # Temperature_Celsius
    # Media_Wearout_Indicator
    info = ["173", "5", "194", "233"]

    for line in output.splitlines():
        # Find only the lines with the attributes
        if line[28:32] != "0x00":
            continue

        # 0 ID
        # 1 ATTRIBUTE_NAME
        # 2 FLAG
        # 3 VALUE
        # 4 WORST
        # 5 THRESH
        # 6 TYPE
        # 7 UPDATED
        # 8 WHEN_FAILED
        # 9 RAW_VALUE
        line = re.sub("\s+", " ", str(line).strip())
        line = line.split(" ")

        value = line[9]
        # try-except is needed in case Rll_Ev_Ct value is messed up
        try:
            value = int(value)
        except Exception:
            continue

        if line[0] in crit and value > 0:
            health[line[1] + "*"] = value
            alert += 1

        if line[0] in info:
            health[line[1]] = value

        if line[8] == "FAILING NOW":
            health[line[1]] = line[8]
            alert += 1

    return alert, health


def queryMDADM(raid):
    p = subprocess.Popen(["/usr/sbin/mdadm", "--detail", "/dev/" + raid], stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    output = output.decode("utf-8")

    if VERBOSE:
        print(output)

    health = {}
    alert = 0

    info = ["Raid Level", "Active Devices", "Working Devices", "Failed Devices"]

    for line in output.splitlines():
        # Find only the lines with the attributes
        # line = set(line.split(" "))

        line = re.sub("\s+", " ", str(line).strip())
        if any(word in line for word in info):
            # if len(line.intersection(info)) > 0:
            # if info in line:
            (key, val) = line.split(":")
            key = key.strip()
            val = val.strip()
            health[key] = val
            if key == "Failed Devices" and int(val) > 0:
                alert += 1
                
        if "/dev/" in line:
            line = line.split(" ")
            if len(line) < 3: continue
            device = [i for i, s in enumerate(line) if '/dev' in s][0]
            health[line[device]] = "/".join(line[4:device])
            
    return alert, health


aggregated = {}
noAlerts = True
DRIVES = ["sdb", "sdc"]
RAIDS = ["md0"]

# Gather HDD health informations
for drive in DRIVES:
    alert, health = querySMART(drive)
    if alert > 0:
        noAlerts = False
        aggregated[drive] = health

for raid in RAIDS:
    alert, health = queryMDADM(raid)
    if alert > 0:
        noAlerts = False
        aggregated[raid] = health

# Exit / Don't send message if no alerts
if noAlerts:
    cPrint("No Alerts on HDD")
    exit(0)
elif not DEBUG:
    cPrint("HDD Alert, sending notice...")

sForm = "{:<10}| {:<36}| {:<10}\n"
text = sForm.format("Device", "Attribute", "Value")
text += ("=" * 60) + "\n"
html = "<tr><th>Device</th><th>Attribute</th><th>Value</th></tr>"

# Merge HDD health status
for drive in aggregated:
    health = aggregated[drive]
    for attr in health:
        value = health[attr]
        text += sForm.format("/dev/" + drive, attr, value)
        html += f"<tr><td>/dev/{drive}</td><td>{attr}</td><td>{value}</td></tr>"

html += f"<tr><td colspan=\"3\">* Pre-fail attributes, replace the disk if > 0</td></tr>"
text += "\n * Pre-fail attributes, replace the disk if > 0"

if DEBUG:
    print(text)
else:
    send("RAID Alert", text)
exit(0)

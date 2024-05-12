#!/usr/bin/env python3

##############################################################################80
# Drive Health Check 20240303
##############################################################################80
# Description: Monitors and records the health of system drives, including
# HDDs, SSDs, and RAIDs. Notifies if there are issues detected with the drives.
# USAGE via CRON: (Runs every 15 minutes)
#   */15 * * * * cd /path/to/folder && ./checkSYS.py 2>&1 | ./tailog.py
# USAGE via CLI:
#   cd /path/to/folder && ./checkSYS.py (-cdqt)
#   Flags:
#       -c: Specifies the CSV file for recording drive health data.
#       -d: Activates debug messages during run, to track progress.
#       -q: Disables push notifications, prints message to terminal.
#       -t: Overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/docs/LICENSE.md for more.
##############################################################################80

import os
import sys
import subprocess
import re
import csv
from datetime import datetime
from collections import namedtuple

from utils import cPrint, getBaseParser, pingHealth, sendNotification, CONF, checkSudo

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Monitors and records the health of system drives.")
args = parser.parse_args()

##############################################################################80
# Configurations
##############################################################################80
datapath = CONF["drives"]["storagePath"]


##############################################################################80
# Queries S.M.A.R.T. data for a given drive.
##############################################################################80
def querySMART(drive):
    p = subprocess.Popen(
        ["/usr/sbin/smartctl", "-a", "/dev/" + drive], stdout=subprocess.PIPE
    )
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


##############################################################################80
# Queries RAID status using mdadm.
##############################################################################80
def queryMDADM(raid):
    p = subprocess.Popen(
        ["/usr/sbin/mdadm", "--detail", "/dev/" + raid], stdout=subprocess.PIPE
    )
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
            if len(line) < 3:
                continue
            device = [i for i, s in enumerate(line) if "/dev" in s][0]
            health[line[device]] = "/".join(line[4:device])

    return alert, health


Drive = namedtuple("Drive", "Name FirstHeard LastHeard Health_Data")


##############################################################################80
# Function to load device databas from CSV
##############################################################################80
def loadDatabase(filepath):
    cPrint("Reading device database...", "BLUE") if args.debug else None
    database = {}
    if not os.path.exists(filepath):
        return False

    with open(filepath, mode="r") as reader:
        # Create a DictReader, and then strip whitespace from the field names
        readCSV = csv.DictReader(
            (line.replace("\0", "") for line in reader), delimiter="|"
        )
        readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

        for row in readCSV:
            cleaned_row = {k: v.strip() for k, v in row.items()}
            database[cleaned_row["Drive"]] = Drive(**cleaned_row)
    return database


##############################################################################80
# Function to save device database to CSV
##############################################################################80
def saveDatabase(filepath, data):
    cPrint("Saving device database...", "BLUE") if args.debug else None
    header = list(data[next(iter(data))]._fields) if data else []

    with open(filepath, "w") as writer:
        writeCSV = csv.writer(writer)
        header = "{:^10}|{:^30}|{:^17}|{:^15}|{:^12}|{:^12}|{:^30}".format(
            *header
        ).split("|", 0)
        writeCSV.writerow(header)

        for mac, details in data.items():
            # Parse the LastHeard date and update the status if it"s more than 30 days ago
            lastHeard = datetime.strptime(
                details.LastHeard, "%Y%m%d%H%M"
            )  # Adjust the format if different

            if lastHeard < thirtyDaysAgo:
                details = details._replace(Status="inactive")

            details = "{:^10}|{:<30}|{:>17}|{:^15}|{:>12}|{:>12}|{:<30}".format(
                *details
            ).split("|", 0)
            writeCSV.writerow(details)
    return True


##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def processScan(scan, database):
    cPrint("Integrating scan into database...", "BLUE") if args.debug else None
    for device in scan:
        mac = device["mac"]
        ip = device["ip"]
        device = database.get(
            mac,
            Device(
                Status="intruder",
                Name="unknown",
                MAC=mac,
                IP=ip,
                FirstHeard=SCANID,
                LastHeard=SCANID,
                Vendor="unknown",
            ),
        )

        if device.Status == "inactive":
            device = device._replace(Status="resurfaced")
        elif device.Status == "resurfaced":
            device = device._replace(Status="active")

        vendor = device.Vendor
        if vendor == "unknown":
            vendor = searchVendor(mac)

        # Update data to the latest scan
        device = device._replace(LastHeard=SCANID, IP=ip, Vendor=vendor)

        # Update the database with the new or updated device
        database[mac] = device

    return database


##############################################################################80
# Pretty print device details
##############################################################################80
def processNewDevices(database):
    cPrint("Processing database for new devices...", "BLUE") if args.debug else None

    newDevices = 0
    message = "<b>New devices:</b>"
    for mac, device in database.items():
        if device.Status != "allowed":
            cPrint(
                f"Device detected: {device.MAC} by {device.Vendor} on {device.IP}",
                "RED",
            )
            newDevices += 1
            ip, vendor = device.IP, device.Vendor
            vendor = f"<font color="  # ff4d3e">{vendor}</font>" if vendor == "unknown" else vendor
            type = "detected" if device.Status == "intruder" else "resurfaced"
            message += f"\n\t - {mac} {type} on {ip} by {vendor}."

    if newDevices or args.test:
        cPrint("New devices found, sending notification...")
        subject = f"{newDevices} new device(s) detected"

        if args.debug:
            cPrint(subject)
            cPrint(message)
        else:
            sendNotification(subject, message)
    else:
        cPrint("No new devices found.", "BLUE")


##############################################################################80
# Begin main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()
    aggregated = {}
    DRIVES = ["sda", "sdb"]
    RAIDS = ["md1"]
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

    data = loadDatabase(datapath)

    data = processScan(scan, data)
    processNewDevices(data)
    saveDatabase(datapath, data)

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

    html += (
        f'<tr><td colspan="3">* Pre-fail attributes, replace the disk if > 0</td></tr>'
    )
    text += "\n * Pre-fail attributes, replace the disk if > 0"

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)


if __name__ == "__main__":
    main()

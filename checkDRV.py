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
import glob
import subprocess
import re
import csv
import math
from datetime import datetime
from collections import namedtuple

from utils import cPrint, getBaseParser, sendNotification, CONF, checkSudo, SCANID

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Monitors and records the health of system drives.")
args = parser.parse_args()

##############################################################################80
# Configurations
##############################################################################80
datapath = CONF["drives"]["storagePath"]
Drive = namedtuple("Drive", "Serial Model Capacity FirstHeard LastHeard Lifetime CurTemp Cycles RALCs")
Health = namedtuple("Health", "SCANID Attributes")

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
    return str(s) + sizes[i]
    
def hoursToHuman(hours):
    days = hours // 24
    remaining_hours = hours % 24
    if days > 0:
        return f"{days}d {remaining_hours}h"
    return f"{remaining_hours}h"    


def findDrives():
    # Lists all SATA and NVMe drives using glob
    sata_drives = glob.glob('/dev/sd?')
    nvme_drives = glob.glob('/dev/nvme?n1')
    return sata_drives + nvme_drives


##############################################################################80
# Queries S.M.A.R.T. data for a given drive.
# ID   | Attribute Title               | Description
# -----|-------------------------------|----------------------------------------------------------------
# 1    | Raw_Read_Error_Rate           | Hardware read errors reported; high values can indicate failing disk surfaces.
# 3    | Spin_Up_Time                  | Average time in milliseconds the drive takes to spin up.
# 5    | Reallocated_Sector_Ct         | Count of sectors moved to the spare area due to read errors.
# 7    | Seek_Error_Rate               | Rate of seek errors; high values may indicate mechanical issues.
# 9    | Power_On_Hours                | Hours the drive has been powered on, indicating age.
# 10   | Spin_Retry_Count              | Count of retry attempts to spin up the drive, indicating start-up issues.
# 12   | Power_Cycle_Count             | Count of full hard disk power on/off cycles.
# 187  | Reported_Uncorrect            | Number of errors uncorrectable by ECC, indicating potential failure.
# 188  | Command_Timeout               | Number of operations not completed in time, can indicate drive failure.
# 189  | High_Fly_Writes               | Count of write operations with the head flying outside its normal range.
# 190  | Airflow_Temperature_Cel       | Measures drive's ambient temperature; higher values may predict failure.
# 191  | G-Sense_Error_Rate            | Count of errors induced by external shock or vibration.
# 192  | Power-Off_Retract_Count       | Count of emergency disk head retract events caused by power loss.
# 193  | Load_Cycle_Count              | Number of load/unload cycles, high values can indicate excessive use.
# 194  | Temperature_Celsius           | Drive's internal temperature, critical for monitoring overheating.
# 195  | Hardware_ECC_Recovered        | Error correction code reports; high counts may indicate disk surface issues.
# 196  | Reallocated_Event_Count       | Count of attempts to transfer data from reallocated sectors to a spare area.
# 197  | Current_Pending_Sector        | Number of unstable sectors waiting to be remapped, indicating potential failure.
# 198  | Offline_Uncorrectable         | Number of uncorrectable errors when read in offline mode, indicating bad sectors.
# 199  | UDMA_CRC_Error_Count          | Count of CRC errors during Ultra DMA mode, can indicate transmission issues.

##############################################################################80
def querySMART(drive):
    cPrint(f"Querying SMART for {drive}...", "BLUE") if args.debug else None
    serial = False
    
    cPrint(output, "BLUE") if args.debug else None  # Print the SMART data if debugging is enabled

    try:
        # output = subprocess.check_output(["/usr/sbin/smartctl", "-a", drive], text=True)
        output = subprocess.check_output(["/usr/sbin/smartctl", "-a", drive], stderr=subprocess.STDOUT, text=True)
        
        cPrint(output, "BLUE") if args.debug else None  # Print the SMART data if debugging is enabled

        # Initialize the return structure
        drive = {}
        health = {}

        # Parse output for hardware info and health data
        for line in output.splitlines():

            if "Serial Number:" in line:
                drive["serial"] = line.split(":")[1].strip()
            elif "Device Model:" in line or "Model Number:" in line:
                drive["model"] = line.split(":")[1].strip()
            elif "User Capacity:" in line:
                # capacity_match = re.search(r'\[.*?(\d+,\d+,\d+|\d+.\d+|\d+) bytes\]', line)
                capacity_match = re.search(r'(\d+,\d+|\d+)', line.replace(',', ''))
                if capacity_match:
                    drive["capacity"] = bytesToHuman(int(capacity_match.group(0).replace(',', '')))
                else:
                    drive["capacity"] = None
            elif "Power_On_Hours" in line:
                lifetime_hours = int(line.split()[-1])
                drive["lifetime"] = hoursToHuman(lifetime_hours)
            elif "Temperature_Celsius" in line:
                temp_match = re.search(r'(\d+)', line.split()[-1])  # Use regex to find the first group of digits
                if temp_match:
                    drive["maxTemp"] = int(temp_match.group(0))  # Convert the first group of digits to int
                else:
                    drive["maxTemp"] = None  # Handle cases where no temperature is found
            elif "Power_Cycle_Count" in line:
                drive["powerCycles"] = int(line.split()[-1])
            elif "Reallocated_Sector_Ct" in line:
                drive["reallocations"] = int(line.split()[-1])

            # Parse S.M.A.R.T. attributes
            attributes = ["1", "3", "5", "7", "9", "10", "12", "187", "188", "189", "190", "191", "192", "193", "194", "195", "196", "197", "198" "199"]
            match = re.match(r'^\s*(\d+)\s+(\w+[\w\s]*\w+)\s+.*\s+(\d+)\s+.*$', line)
            if match:
                attr_id, attr_name, raw_value = match.groups()
                try:
                    value = int(raw_value)
                    if attr_id in attributes:  # Critical attributes
                        health[attr_id] = value
                except ValueError:
                    continue
                
        # return drive, health
        return drive

    except subprocess.CalledProcessError as e:
        cPrint(f"SMART query failed for {drive}: {e.output}", "RED")
        return False

##############################################################################80
# Queries RAID status using mdadm.
##############################################################################80
def queryMDADM(raid):
    cPrint("Querying MDADM...", "BLUE") if args.debug else None
    
    p = subprocess.Popen(["/usr/sbin/mdadm", "--detail", "/dev/" + raid], stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    output = output.decode("utf-8")

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
        readCSV = csv.DictReader((line.replace("\0", "") for line in reader), delimiter="|")
        readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

        for row in readCSV:
            cleaned_row = {k: v.strip() for k, v in row.items()}
            database[cleaned_row["Serial"]] = Drive(**cleaned_row)
    return database

##############################################################################80
# Function to save device database to CSV
##############################################################################80
def saveDatabase(filepath, database):
    cPrint("Saving device database...", "BLUE") if args.debug else None
    header = list(database[next(iter(database))]._fields) if database else []

    with open(filepath, "w") as writer:
        writeCSV = csv.writer(writer)
        header = "{:^16}|{:^22}|{:^8}|{:^14}|{:^14}|{:^10}|{:^8}|{:^8}|{:^6}".format(*header).split("|", 0)
        writeCSV.writerow(header)

        for serial, drive in database.items():
            # Parse the LastHeard date and update the status if it"s more than 30 days ago
            lastHeard = datetime.strptime(drive.LastHeard, "%Y%m%d%H%M")  # Adjust the format if different

            row = "{:<16}|{:<22}|{:>8}|{:^14}|{:^14}|{:^10}|{:>8}|{:>8}|{:<6}".format(*drive).split("|", 0)
            writeCSV.writerow(row)
    return True

##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def processDrives(drives, database):
    cPrint("Integrating scan into database...", "BLUE") if args.debug else None
    for drive in drives:
        drive = drives[drive]
        serial = drive["serial"]

        device = database.get(serial, Drive(
                        Serial=serial,
                        Model=drive["model"],
                        Capacity=drive["capacity"],
                        FirstHeard=SCANID,
                        LastHeard=SCANID,
                        Lifetime=drive["lifetime"],
                        CurTemp=drive["maxTemp"],
                        Cycles=drive["powerCycles"],
                        RALCs=drive["reallocations"]))

        # Update data to the latest scan
        device = device._replace(LastHeard=SCANID)
        print(device)
        
        # Update the database with the new or updated device
        database[serial] = device

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
            cPrint(f"Device detected: {device.MAC} by {device.Vendor} on {device.IP}", "RED")
            newDevices += 1
            ip, vendor = device.IP, device.Vendor
            vendor = f"<font color="#ff4d3e">{vendor}</font>" if vendor == "unknown" else vendor
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
    DRIVES = ["sda", "sdb", "sdc", "sdd", "sde", "sdf"]
    RAIDS = ["md1"]
    # Gather HDD health informations
    drives = findDrives()
    cPrint(drives)
    for drive in drives:
        health = querySMART(drive)
        if health:
            aggregated[drive] = health

    # for raid in RAIDS:
    #   alert, health = queryMDADM(raid)
    #   aggregated[raid] = health

    data = loadDatabase(datapath)
    
    data = processDrives(aggregated, data)
    saveDatabase(datapath, data)

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)

if __name__ == "__main__":
    main()
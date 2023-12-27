#!/usr/bin/env python3

##############################################################################80
# Network Intrusion Scan 20231224
##############################################################################80
# This script will scan the network of your choice and will alert you of devices
# not listed as "allowed" in the database. The alerts are sent through PushOver.
# By default, all devices will show as untrusted.
# USAGE via CRON: (Runs every 10 minutes, must be ROOT user)
#   */10 * * * * cd /path/to/folder && ./checkNET.py 2>&1
# USAGE via CLI:
#   cd /path/to/folder && ./checkNET.py (-dn)
#   Flags:  -d: prints debug messages and doesn't send notification
#           -n: to use a cached nmap scan, created on first run
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/docs/LICENSE.md for more.
##############################################################################80

import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import csv
import requests
from collections import namedtuple
from datetime import datetime, timedelta
from utils import checkSudo, cPrint, formatIP, getBaseParser, sendNotification, SCANID

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Scans network range for unregistered devices.")
parser.add_argument("-n", "--noscan", action="store_true", help="Uses cached scanlog, requires initial run.")
args = parser.parse_args()


##############################################################################80
# Configurations
##############################################################################80
scanpath = "data/scanlog.xml"
datapath = "data/devices.csv"
netRange = "192.168.1.1/24"
thirtyDaysAgo = datetime.now() - timedelta(days=30)

##############################################################################80
# Launch NMAP and scan the network mask provided
##############################################################################80
def getNmapScan(netRange, scanlog):
    cPrint("Running NMAP scan on network range...", "BLUE") if args.debug else None

    # Run nmap scan of netRange, save xml to scanlog file
    if not args.noscan:
        try:
            subprocess.run(["sudo", "nmap", "-v", "-sn", netRange, "-oX", scanlog], check=True, capture_output=True)

        except subprocess.CalledProcessError as e:
            cPrint(f"Error running nmap: {e}", "RED")
            sys.exit(127)

    # Open scanlog file and find root
    try:
        root = ET.parse(scanlog).getroot()
    except ET.ParseError as e:
        cPrint(f"Error parsing scanlog: {e}", "RED")
        sys.exit(1)

    hosts = root.findall("./host")
    if not hosts:
        return {}

    scan = []
    for child in hosts:
        state = mac = ip = vendor = ""
        for attrib in child:
            if attrib.tag == "status":
                state = attrib.attrib["state"]
            if attrib.tag == "address":
                if attrib.attrib["addrtype"] == "mac":
                     mac = attrib.attrib["addr"]
                if attrib.attrib["addrtype"] == "ipv4":
                    ip = formatIP(attrib.attrib["addr"])
                if "vendor" in attrib.attrib:
                    vendor = attrib.attrib["vendor"]
                else:
                    vendor = "unknown"
        if state == "down":
            continue

        if mac == "":
            continue

        if args.debug:
            cPrint(f"{mac}\t{vendor}\t{ip}")

        scan.append({"mac": mac, "vendor": vendor, "ip": ip})

    return scan


Device = namedtuple("Device", ("Status Name MAC IP FirstHeard LastHeard Vendor"))
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
            database[cleaned_row["MAC"]] = Device(**cleaned_row)
    return database
    
##############################################################################80
# Function to save device database to CSV
##############################################################################80
def saveDatabase(filepath, data):
    cPrint("Saving device database...", "BLUE") if args.debug else None
    header = list(data[next(iter(data))]._fields) if data else []

    with open(filepath, "w") as writer:
        writeCSV = csv.writer(writer)
        header = "{:^10}|{:^30}|{:^17}|{:^15}|{:^12}|{:^12}|{:^30}".format(*header).split("|", 0)
        writeCSV.writerow(header)

        for mac, details in data.items():
            # Parse the LastHeard date and update the status if it"s more than 30 days ago
            lastHeard = datetime.strptime(details.LastHeard, "%Y%m%d%H%M")  # Adjust the format if different

            if lastHeard < thirtyDaysAgo:
                details = details._replace(Status="inactive")

            details = "{:^10}|{:<30}|{:>17}|{:^15}|{:>12}|{:>12}|{:<30}".format(*details).split("|", 0)
            writeCSV.writerow(details)
    return True

##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def searchVendor(mac):
    cPrint("Searching MAC against vendor API...", "BLUE") if args.debug else None
    url = f"https://api.macvendors.com/{mac}"
    try:
        response = requests.get(url)
        if DEBUG:
            cPrint(response.text)
        if response.status_code == 200:
            return response.text  # The vendor name
        else:
            return "unknown"
    except requests.RequestException:
        return "failed"

##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def processScan(scan, database):
    cPrint("Integrating scan into database...", "BLUE") if args.debug else None
    for device in scan:
        mac = device["mac"]
        ip = device["ip"]
        device = database.get(mac, Device(Status="intruder", Name="unknown", MAC=mac, IP=ip, FirstHeard=SCANID, LastHeard=SCANID, Vendor="unknown"))

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
# Being Main execution
##############################################################################80
def main():
    cPrint("Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()

    scan = getNmapScan(netRange, scanpath)
    data = loadDatabase(datapath)
    
    data = processScan(scan, data)
    processNewDevices(data)
    saveDatabase(datapath, data)

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)   

if __name__ == "__main__":
    main()
